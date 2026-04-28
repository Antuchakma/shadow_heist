import math
import random
import sys

import pygame

# ============================================================
# CONFIG
# ============================================================
GRID = 8
TILE = 74
W, H = 1680, 960
FPS = 60
MAX_DETECTION = 100

EMPTY, LOOT, ALARM, GUARD, EXIT = range(5)

TILE_FACE = {
    EMPTY: (30, 34, 58),
    LOOT: (220, 170, 42),
    ALARM: (205, 72, 92),
    GUARD: (110, 90, 235),
    EXIT: (50, 205, 120),
}
TILE_SHADOW = {
    EMPTY: (14, 17, 30),
    LOOT: (124, 91, 18),
    ALARM: (120, 33, 48),
    GUARD: (58, 45, 135),
    EXIT: (22, 98, 58),
}
TILE_ACCENT = {
    EMPTY: (84, 92, 135),
    LOOT: (255, 231, 122),
    ALARM: (255, 166, 178),
    GUARD: (192, 180, 255),
    EXIT: (145, 255, 190),
}
TILE_LABEL = {
    EMPTY: "",
    LOOT: "LOOT",
    ALARM: "ALARM",
    GUARD: "GUARD",
    EXIT: "EXIT",
}
TILE_ICON = {
    EMPTY: "",
    LOOT: "[$]",
    ALARM: "[!]",
    GUARD: "[G]",
    EXIT: "[X]",
}

POWER_CLOAK = "cloak"
POWERS = {
    POWER_CLOAK: {"cost": 20, "name": "CLOAK", "duration": 2, "col": (125, 250, 255)}
}

LOOT_RATIO = 0.30
HAZARD_RATIO = 0.40
BASE_DETECTION_STEP = 0


# ============================================================
# FONT CACHE
# ============================================================
_FONTS = {}


def F(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = pygame.font.SysFont("Arial", size, bold=bold)
    return _FONTS[key]


# ============================================================
# DRAW HELPERS
# ============================================================
def draw_3d_rect(surf, face, shadow, rect, depth=5, radius=8):
    x, y, w, h = rect
    pygame.draw.rect(surf, shadow, (x + depth, y + depth, w, h), border_radius=radius)
    pygame.draw.rect(surf, face, (x, y, w, h), border_radius=radius)
    hi = tuple(min(255, c + 55) for c in face)
    pygame.draw.line(surf, hi, (x + radius, y + 1), (x + w - radius, y + 1), 2)
    pygame.draw.line(surf, hi, (x + 1, y + radius), (x + 1, y + h - radius), 2)


def draw_bar(surf, x, y, w, h, val, maxv, fg, bg=(24, 28, 46), radius=6):
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=radius)
    filled = max(0, int(w * min(val, maxv) / maxv))
    if filled:
        pygame.draw.rect(surf, fg, (x, y, filled, h), border_radius=radius)
        glow = tuple(min(255, c + 70) for c in fg)
        pygame.draw.rect(surf, glow, (x, y, filled, max(2, h // 3)), border_radius=radius)
    pygame.draw.rect(surf, (72, 78, 118), (x, y, w, h), 1, border_radius=radius)


def rshadow(surf, text, font, color, x, y, shadow=(0, 0, 0), off=2):
    surf.blit(font.render(text, True, shadow), (x + off, y + off))
    surf.blit(font.render(text, True, color), (x, y))


def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def shift_col(col, amount):
    return tuple(clamp(c + amount, 0, 255) for c in col)


# ============================================================
# AGENT
# ============================================================
class Agent:
    def __init__(self, name, color, pos):
        self.name = name
        self.color = color
        self.r, self.c = pos
        self.loot = 0
        self.banked_loot = 0
        self.detection = 0
        self.alive = True
        self.resources = 0
        self.active_powers = {}
        self.last_action = ""
        self.last_pos = None
        self.power_flash = 0
        self.power_flash_col = (255, 255, 255)
        self.power_name_disp = ""
        self.effect_text_timer = 0
        self.effect_particles = []

    def pos(self):
        return (self.r, self.c)

    def risk_level(self):
        if self.detection >= 85:
            return "CRITICAL"
        if self.detection >= 60:
            return "HIGH"
        if self.detection >= 35:
            return "MEDIUM"
        if self.detection >= 15:
            return "LOW"
        return "SAFE"

    def risk_color(self):
        t = self.detection / MAX_DETECTION
        if t < 0.5:
            return lerp_col((70, 220, 150), (255, 210, 90), t / 0.5)
        return lerp_col((255, 210, 90), (255, 72, 72), (t - 0.5) / 0.5)

    def has_power(self, power):
        return self.active_powers.get(power, 0) > 0

    def activate_power(self, power):
        data = POWERS[power]
        if self.resources < data["cost"]:
            return False
        self.resources -= data["cost"]
        self.active_powers[power] = data["duration"]
        self.power_flash = 64
        self.power_flash_col = data["col"]
        self.power_name_disp = data["name"]
        self.effect_text_timer = 54
        self.spawn_effect_particles(data["col"], 22)
        return True

    def update_powers(self):
        for power in list(self.active_powers.keys()):
            self.active_powers[power] -= 1
            if self.active_powers[power] <= 0:
                del self.active_powers[power]

    def spawn_effect_particles(self, color, count):
        for _ in range(count):
            angle = random.random() * math.tau
            speed = random.uniform(0.9, 2.8)
            self.effect_particles.append(
                {
                    "x": 0.0,
                    "y": 0.0,
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed,
                    "life": random.randint(18, 34),
                    "max_life": 34,
                    "color": color,
                    "size": random.randint(2, 4),
                }
            )

    def tick_visuals(self):
        if self.power_flash > 0:
            self.power_flash -= 1
        if self.effect_text_timer > 0:
            self.effect_text_timer -= 1
        updated = []
        for p in self.effect_particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            p["vx"] *= 0.96
            p["vy"] *= 0.96
            if p["life"] > 0:
                updated.append(p)
        self.effect_particles = updated


# ============================================================
# GAME
# ============================================================
class Game:
    def __init__(self):
        self.turn = 0
        self.max_turn = 60
        self.over = False
        self.log = []
        self.winner = ""

        self.player_grid = [[EMPTY] * GRID for _ in range(GRID)]
        self.opponent_grid = [[EMPTY] * GRID for _ in range(GRID)]
        self.player_visited = [[False] * GRID for _ in range(GRID)]
        self.opponent_visited = [[False] * GRID for _ in range(GRID)]
        self.player_reveal = [[None] * GRID for _ in range(GRID)]
        self.opponent_reveal = [[None] * GRID for _ in range(GRID)]

        self.player_moves = 0
        self.opponent_moves = 0

        self.alarm_levels = {}
        self.guard_levels = {}
        self.loot_tiles = []
        self.hazard_tiles = []

        cells = [(r, c) for r in range(GRID) for c in range(GRID)]
        random.shuffle(cells)
        total_cells = GRID * GRID
        loot_count = int(total_cells * LOOT_RATIO)
        hazard_count = int(total_cells * HAZARD_RATIO)
        alarm_count = hazard_count // 2
        guard_count = hazard_count - alarm_count

        idx = 0
        self.loot_tiles = cells[idx:idx + loot_count]
        idx += loot_count
        alarm_tiles = cells[idx:idx + alarm_count]
        idx += alarm_count
        guard_tiles = cells[idx:idx + guard_count]

        for pos in alarm_tiles:
            self.alarm_levels[pos] = random.choice([18, 22, 26, 30])
        for pos in guard_tiles:
            self.guard_levels[pos] = random.choice([22, 28, 32, 36])
        self.hazard_tiles = alarm_tiles + guard_tiles

        for grid in (self.player_grid, self.opponent_grid):
            for r, c in self.loot_tiles:
                grid[r][c] = LOOT
            for r, c in alarm_tiles:
                grid[r][c] = ALARM
            for r, c in guard_tiles:
                grid[r][c] = GUARD

        self.exitA = self._edge([])
        self.exitB = self._edge([self.exitA])
        self.player_grid[self.exitA[0]][self.exitA[1]] = EXIT
        self.opponent_grid[self.exitB[0]][self.exitB[1]] = EXIT

        player_start = self._edge([self.exitA])
        opponent_start = self._edge([self.exitA, self.exitB, player_start])

        self.player = Agent("Shadow", (100, 214, 255), player_start)
        self.opponent = Agent("Phantom", (255, 160, 98), opponent_start)

        for pos, visited, reveal, grid in (
            (player_start, self.player_visited, self.player_reveal, self.player_grid),
            (self.exitA, self.player_visited, self.player_reveal, self.player_grid),
            (opponent_start, self.opponent_visited, self.opponent_reveal, self.opponent_grid),
            (self.exitB, self.opponent_visited, self.opponent_reveal, self.opponent_grid),
        ):
            r, c = pos
            visited[r][c] = True
            reveal[r][c] = grid[r][c]

        self.log.append("Board ready: 30% loot tiles, 40% alarm or guard tiles.")
        self.log.append("CLOAK is the only special power and costs 20 resources.")
        self.log.append("Every 2 moves, the resource bar gains +10.")

    def _edge(self, exclude):
        edges = list(
            set(
                [(0, c) for c in range(GRID)]
                + [(GRID - 1, c) for c in range(GRID)]
                + [(r, 0) for r in range(GRID)]
                + [(r, GRID - 1) for r in range(GRID)]
            )
        )
        edges = [pos for pos in edges if pos not in exclude]
        return random.choice(edges)

    def neighbors(self, r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < GRID and 0 <= nc < GRID:
                yield nr, nc

    def hazard_level(self, tile, pos):
        if tile == ALARM:
            return self.alarm_levels.get(pos, 20)
        if tile == GUARD:
            return self.guard_levels.get(pos, 28)
        return 0

    def resource_tick(self, agent, is_player):
        if is_player:
            self.player_moves += 1
            move_count = self.player_moves
        else:
            self.opponent_moves += 1
            move_count = self.opponent_moves
        if move_count % 2 == 0:
            agent.resources = min(100, agent.resources + 10)
            self.log.append(f"{agent.name}: resource bar +10 -> {agent.resources}")

    def eliminate_agent(self, agent):
        if agent.alive:
            agent.alive = False
            self.log.append(f"*** {agent.name} LOST! Detection reached {agent.detection}. ***")

    def apply_tile(self, agent, grid, visited, reveal):
        r, c = agent.r, agent.c
        tile = grid[r][c]
        pos = (r, c)

        if visited is not None:
            visited[r][c] = True
        if reveal is not None and reveal[r][c] is None:
            reveal[r][c] = tile

        if tile == LOOT:
            gained = random.choice([12, 14, 16, 18])
            agent.loot += gained
            grid[r][c] = EMPTY
            agent.last_action = f"Grabbed LOOT (+{gained})"
            self.log.append(f"{agent.name}: {agent.last_action}")

        elif tile in (ALARM, GUARD):
            level = self.hazard_level(tile, pos)
            if agent.has_power(POWER_CLOAK):
                agent.last_action = f"{TILE_LABEL[tile]} bypassed by CLOAK"
                self.log.append(f"{agent.name}: {agent.last_action}")
            else:
                agent.detection = min(MAX_DETECTION, agent.detection + level)
                kind = "Alarm triggered" if tile == ALARM else "Guard spotted movement"
                agent.last_action = f"{kind} (+{level} detection)"
                self.log.append(f"{agent.name}: {agent.last_action}")

        elif tile == EXIT:
            if agent.loot > 0:
                banked = agent.loot
                agent.banked_loot += banked
                agent.loot = 0
                agent.last_action = f"Escaped with {banked} loot (Total {agent.banked_loot})"
                self.log.append(f"{agent.name}: {agent.last_action}")
            else:
                agent.last_action = "Reached exit"

        if agent.detection >= MAX_DETECTION:
            self.eliminate_agent(agent)

    def move_agent(self, agent, grid, visited, reveal, nr, nc, is_player):
        agent.last_pos = (agent.r, agent.c)
        agent.r, agent.c = nr, nc
        self.apply_tile(agent, grid, visited, reveal)
        agent.update_powers()
        self.resource_tick(agent, is_player)

    def is_over(self):
        return self.turn >= self.max_turn or not self.player.alive or not self.opponent.alive

    def winner_text(self):
        if not self.player.alive and not self.opponent.alive:
            return "TIE - Both agents were caught"
        if not self.player.alive:
            return f"PHANTOM WINS - Shadow hit {MAX_DETECTION} detection"
        if not self.opponent.alive:
            return f"SHADOW WINS - Phantom hit {MAX_DETECTION} detection"

        player_total = self.player.banked_loot + self.player.loot
        opponent_total = self.opponent.banked_loot + self.opponent.loot
        if player_total > opponent_total:
            return f"SHADOW WINS - {player_total} loot vs {opponent_total}"
        if opponent_total > player_total:
            return f"PHANTOM WINS - {opponent_total} loot vs {player_total}"
        return f"TIE - Both agents hold {player_total} loot"


# ============================================================
# AI
# ============================================================
def tile_priority(game, tile, pos, agent):
    if tile == LOOT:
        return 100
    if tile == EXIT and agent.loot > 0:
        return 90 + min(agent.loot, 30)
    if tile == ALARM:
        return -game.alarm_levels.get(pos, 18)
    if tile == GUARD:
        return -game.guard_levels.get(pos, 24) - 5
    return 10


def should_use_cloak(game, agent, grid):
    if agent.has_power(POWER_CLOAK) or agent.resources < POWERS[POWER_CLOAK]["cost"]:
        return False

    risky_neighbors = 0
    for nr, nc in game.neighbors(agent.r, agent.c):
        if grid[nr][nc] in (ALARM, GUARD):
            risky_neighbors += 1

    return agent.detection >= 55 or risky_neighbors >= 2


def pick_best_move(game, agent, grid, visited):
    best_score = -10**9
    best_pos = None
    for nr, nc in game.neighbors(agent.r, agent.c):
        pos = (nr, nc)
        tile = grid[nr][nc]
        score = tile_priority(game, tile, pos, agent)
        if not visited[nr][nc]:
            score += 18
        if agent.last_pos and pos == agent.last_pos:
            score -= 14

        dist_to_exit = abs(nr - (game.exitA[0] if agent.name == "Shadow" else game.exitB[0])) + abs(
            nc - (game.exitA[1] if agent.name == "Shadow" else game.exitB[1])
        )
        if agent.loot >= 24:
            score -= dist_to_exit * 2
        else:
            score -= dist_to_exit * 0.3

        if tile in (ALARM, GUARD) and agent.has_power(POWER_CLOAK):
            score += 25

        if score > best_score:
            best_score = score
            best_pos = pos
    return best_pos


def shadow_turn(game):
    agent = game.player
    if should_use_cloak(game, agent, game.player_grid) and agent.activate_power(POWER_CLOAK):
        game.log.append(f"{agent.name}: CLOAK activated (-20 resources)")

    move = pick_best_move(game, agent, game.player_grid, game.player_visited)
    if move:
        game.move_agent(agent, game.player_grid, game.player_visited, game.player_reveal, move[0], move[1], True)


def phantom_turn(game):
    agent = game.opponent
    if should_use_cloak(game, agent, game.opponent_grid) and agent.activate_power(POWER_CLOAK):
        game.log.append(f"{agent.name}: CLOAK activated (-20 resources)")

    move = pick_best_move(game, agent, game.opponent_grid, game.opponent_visited)
    if move:
        game.move_agent(
            agent,
            game.opponent_grid,
            game.opponent_visited,
            game.opponent_reveal,
            move[0],
            move[1],
            False,
        )


# ============================================================
# PROBABILITY MAP
# ============================================================
def build_prob_map(grid, visited):
    remaining = {LOOT: 0, ALARM: 0, GUARD: 0}
    hidden = 0
    for r in range(GRID):
        for c in range(GRID):
            if not visited[r][c]:
                hidden += 1
                tile = grid[r][c]
                if tile in remaining:
                    remaining[tile] += 1

    prob = [[None] * GRID for _ in range(GRID)]
    for r in range(GRID):
        for c in range(GRID):
            if visited[r][c] or hidden == 0:
                prob[r][c] = {LOOT: 0.0, ALARM: 0.0, GUARD: 0.0}
            else:
                prob[r][c] = {
                    LOOT: remaining[LOOT] / hidden,
                    ALARM: remaining[ALARM] / hidden,
                    GUARD: remaining[GUARD] / hidden,
                }
    return prob


# ============================================================
# RENDER
# ============================================================
DEPTH = 4


def draw_background(surf, frame):
    surf.fill((9, 11, 22))
    for i in range(16):
        alpha = 22 + int(10 * math.sin(frame * 0.02 + i))
        glow = pygame.Surface((260, 260), pygame.SRCALPHA)
        pygame.draw.circle(glow, (90, 60 + i * 4, 180, alpha), (130, 130), 130)
        surf.blit(glow, (i * 120 - 50, 40 + (i % 4) * 180))


def draw_loot_visual(surf, rx, ry, rw, rh, collected):
    gold = (255, 220, 90) if not collected else (170, 145, 88)
    shine = shift_col(gold, 30)
    dark = shift_col(gold, -80)
    base_y = ry + rh // 2 + 6
    chest = pygame.Rect(rx + 16, base_y, rw - 32, 20)
    lid = pygame.Rect(rx + 18, base_y - 14, rw - 36, 16)
    pygame.draw.rect(surf, dark, (chest.x + 3, chest.y + 4, chest.w, chest.h), border_radius=6)
    pygame.draw.rect(surf, gold, chest, border_radius=6)
    pygame.draw.rect(surf, shine, lid, border_radius=6)
    pygame.draw.rect(surf, dark, (rx + rw // 2 - 6, base_y + 4, 12, 10), border_radius=3)
    for dx in (-16, -6, 5, 15):
        pygame.draw.circle(surf, shine, (rx + rw // 2 + dx, base_y - 4 - abs(dx) // 5), 5)
    pygame.draw.line(surf, dark, (chest.x + 6, chest.y + 10), (chest.right - 6, chest.y + 10), 2)


def draw_alarm_visual(surf, rx, ry, rw, rh, collected, frame):
    red = (255, 100, 126) if not collected else (140, 92, 104)
    red_hi = shift_col(red, 40)
    red_dark = shift_col(red, -90)
    cx, cy = rx + rw // 2, ry + rh // 2 + 2
    pulse = 2 + int(2 * math.sin(frame * 0.18))
    if not collected:
        glow = pygame.Surface((72, 72), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*red, 38), (36, 36), 18 + pulse)
        surf.blit(glow, (cx - 36, cy - 36))
    pygame.draw.rect(surf, red_dark, (cx - 18, cy + 12, 36, 8), border_radius=4)
    pygame.draw.circle(surf, red, (cx, cy), 16)
    pygame.draw.circle(surf, red_hi, (cx - 5, cy - 5), 7)
    pygame.draw.arc(surf, red_dark, (cx - 20, cy - 16, 40, 18), math.pi, math.tau, 3)
    pygame.draw.line(surf, red_dark, (cx - 11, cy + 17), (cx - 11, cy + 28), 2)
    pygame.draw.line(surf, red_dark, (cx + 11, cy + 17), (cx + 11, cy + 28), 2)


def draw_guard_visual(surf, rx, ry, rw, rh, collected):
    suit = (170, 156, 255) if not collected else (122, 114, 156)
    suit_dark = shift_col(suit, -70)
    visor = (130, 225, 255) if not collected else (90, 140, 150)
    cx, cy = rx + rw // 2, ry + rh // 2 + 1
    pygame.draw.circle(surf, suit_dark, (cx, cy - 10), 14)
    pygame.draw.circle(surf, suit, (cx, cy - 12), 14)
    pygame.draw.rect(surf, visor, (cx - 9, cy - 17, 18, 7), border_radius=3)
    pygame.draw.rect(surf, suit_dark, (cx - 14, cy + 1, 28, 20), border_radius=8)
    pygame.draw.rect(surf, suit, (cx - 16, cy - 1, 32, 20), border_radius=8)
    pygame.draw.line(surf, suit_dark, (cx - 10, cy + 18), (cx - 14, cy + 31), 3)
    pygame.draw.line(surf, suit_dark, (cx + 10, cy + 18), (cx + 14, cy + 31), 3)
    pygame.draw.line(surf, suit_dark, (cx - 16, cy + 4), (cx - 24, cy + 16), 3)
    pygame.draw.line(surf, suit_dark, (cx + 16, cy + 4), (cx + 24, cy + 16), 3)
    pygame.draw.circle(surf, visor, (cx + 26, cy - 12), 4)
    pygame.draw.line(surf, visor, (cx + 18, cy - 7), (cx + 26, cy - 12), 2)


def draw_exit_visual(surf, rx, ry, rw, rh, collected):
    door = (88, 230, 155) if not collected else (80, 120, 92)
    frame_col = shift_col(door, -70)
    pygame.draw.rect(surf, frame_col, (rx + 20, ry + 14, rw - 40, rh - 24), border_radius=8)
    pygame.draw.rect(surf, door, (rx + 25, ry + 18, rw - 50, rh - 30), border_radius=8)
    pygame.draw.circle(surf, (230, 255, 230), (rx + rw - 28, ry + rh // 2), 3)
    pygame.draw.line(surf, (230, 255, 230), (rx + 32, ry + rh // 2), (rx + rw - 40, ry + rh // 2), 3)
    pygame.draw.polygon(
        surf,
        (230, 255, 230),
        [(rx + rw - 44, ry + rh // 2 - 8), (rx + rw - 26, ry + rh // 2), (rx + rw - 44, ry + rh // 2 + 8)],
    )


def draw_tile_3d(surf, r, c, x0, y0, tile_type, is_hidden=False, collected=False, level_text=""):
    x = x0 + c * TILE
    y = y0 + r * TILE
    pad = 3
    rx, ry, rw, rh = x + pad, y + pad, TILE - pad * 2, TILE - pad * 2

    if is_hidden:
        face = (31, 35, 60)
        shadow = (16, 19, 34)
    elif collected:
        face = tuple(max(0, v - 75) for v in TILE_FACE[tile_type])
        shadow = tuple(max(0, v - 40) for v in TILE_SHADOW[tile_type])
    else:
        face = TILE_FACE[tile_type]
        shadow = TILE_SHADOW[tile_type]

    for depth in range(DEPTH, 0, -1):
        shade = tuple(max(0, int(shadow[i] * (1 - depth * 0.14))) for i in range(3))
        pygame.draw.rect(surf, shade, (rx + depth, ry + depth, rw, rh), border_radius=8)
    pygame.draw.rect(surf, face, (rx, ry, rw, rh), border_radius=8)
    pygame.draw.rect(surf, tuple(min(255, v + 36) for v in face), (rx, ry, rw, rh), 1, border_radius=8)

    if is_hidden:
        q = F(24, bold=True).render("?", True, (102, 112, 160))
        surf.blit(q, (rx + rw // 2 - q.get_width() // 2, ry + rh // 2 - q.get_height() // 2))
        return

    label = TILE_LABEL.get(tile_type, "")
    accent = TILE_ACCENT.get(tile_type, (220, 220, 220))
    if collected:
        accent = tuple(max(0, c - 70) for c in accent)
        label = f"{label} done"

    if tile_type == LOOT:
        draw_loot_visual(surf, rx, ry, rw, rh, collected)
    elif tile_type == ALARM:
        draw_alarm_visual(surf, rx, ry, rw, rh, collected, pygame.time.get_ticks() // 16)
    elif tile_type == GUARD:
        draw_guard_visual(surf, rx, ry, rw, rh, collected)
    elif tile_type == EXIT:
        draw_exit_visual(surf, rx, ry, rw, rh, collected)

    if label:
        lt = F(12, bold=True).render(label, True, accent)
        surf.blit(lt, (rx + rw // 2 - lt.get_width() // 2, ry + rh - 20))
    if level_text:
        lv = F(12, bold=True).render(level_text, True, (255, 245, 255))
        surf.blit(lv, (rx + rw // 2 - lv.get_width() // 2, ry + rh // 2 - lv.get_height() // 2))


def draw_prob_overlay(surf, r, c, x0, y0, prob_map):
    x = x0 + c * TILE + 3
    y = y0 + r * TILE + 3
    rw = TILE - 6
    rh = TILE - 6
    p = prob_map[r][c]
    lines = [
        (f"L:{int(p[LOOT] * 100)}%", (255, 225, 90)),
        (f"A:{int(p[ALARM] * 100)}%", (255, 132, 150)),
        (f"G:{int(p[GUARD] * 100)}%", (196, 182, 255)),
    ]
    font = F(12, bold=True)
    total_h = len(lines) * 15
    sy = y + rh // 2 - total_h // 2
    for i, (text, col) in enumerate(lines):
        width = font.render(text, True, (0, 0, 0)).get_width()
        rshadow(surf, text, font, col, x + rw // 2 - width // 2, sy + i * 15)


def draw_agent_circle(surf, agent, x0, y0, frame):
    cx = x0 + agent.c * TILE + TILE // 2
    cy = y0 + agent.r * TILE + TILE // 2

    if agent.has_power(POWER_CLOAK):
        pulse = int(24 + 5 * math.sin(frame * 0.22))
        aura = pygame.Surface((pulse * 3, pulse * 3), pygame.SRCALPHA)
        pygame.draw.circle(aura, (125, 250, 255, 44), (pulse * 3 // 2, pulse * 3 // 2), pulse + 18)
        pygame.draw.circle(aura, (125, 250, 255, 24), (pulse * 3 // 2, pulse * 3 // 2), pulse + 28)
        surf.blit(aura, (cx - aura.get_width() // 2, cy - aura.get_height() // 2))

    for particle in agent.effect_particles:
        alpha = int(255 * (particle["life"] / particle["max_life"]))
        col = (*particle["color"], alpha)
        psurf = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(psurf, col, (9, 9), particle["size"])
        surf.blit(psurf, (cx + particle["x"] - 9, cy + particle["y"] - 9))

    if agent.power_flash > 0:
        frac = agent.power_flash / 64
        ring_r = int(20 + 26 * frac)
        rc = agent.power_flash_col
        rs = pygame.Surface((ring_r * 2 + 6, ring_r * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(rs, (*rc, int(210 * frac)), (ring_r + 3, ring_r + 3), ring_r, 3)
        surf.blit(rs, (cx - ring_r - 3, cy - ring_r - 3))

    pygame.draw.circle(surf, (0, 0, 0), (cx + 3, cy + 3), 20)
    dark = tuple(max(0, v - 65) for v in agent.color)
    pygame.draw.circle(surf, dark, (cx, cy), 21)
    pygame.draw.circle(surf, agent.color, (cx, cy), 18)
    pygame.draw.circle(surf, tuple(min(255, v + 80) for v in agent.color), (cx - 5, cy - 6), 7)
    pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 18, 2)

    init = F(15, bold=True).render(agent.name[0], True, (9, 10, 20))
    surf.blit(init, (cx - init.get_width() // 2, cy - init.get_height() // 2))

    if agent.effect_text_timer > 0:
        alpha_col = tuple(clamp(v + 30, 0, 255) for v in agent.power_flash_col)
        txt = agent.power_name_disp or "CLOAK"
        width = F(15, bold=True).render(txt, True, alpha_col).get_width()
        y = cy - 48 - int((54 - agent.effect_text_timer) * 0.35)
        rshadow(surf, txt, F(15, bold=True), alpha_col, cx - width // 2, y)


def draw_grid_view(surf, game, agent, grid, visited, reveal, x0, y0, label_str, prob_map, frame):
    pw = GRID * TILE + 18
    ph = GRID * TILE + 18
    draw_3d_rect(surf, (21, 24, 45), (9, 11, 24), (x0 - 9, y0 - 9, pw, ph), depth=7, radius=12)

    pygame.draw.rect(surf, (18, 20, 38), (x0 - 9, y0 - 42, pw, 34), border_radius=9)
    pygame.draw.rect(surf, agent.color, (x0 - 9, y0 - 42, pw, 34), 2, border_radius=9)
    label_font = F(16, bold=True)
    width = label_font.render(label_str, True, (0, 0, 0)).get_width()
    rshadow(surf, label_str, label_font, agent.color, x0 + pw // 2 - width // 2 - 9, y0 - 36)

    for r in range(GRID):
        for c in range(GRID):
            original = reveal[r][c]
            current = grid[r][c]
            visible = visited[r][c]
            if visible:
                tile = original if original is not None else current
                collected = current == EMPTY and tile not in (EMPTY, EXIT)
                level_text = ""
                if tile == ALARM:
                    level_text = f"+{game.alarm_levels.get((r, c), 18)}"
                elif tile == GUARD:
                    level_text = f"+{game.guard_levels.get((r, c), 24)}"
                draw_tile_3d(surf, r, c, x0, y0, tile, False, collected, level_text if not collected else "")
            else:
                draw_tile_3d(surf, r, c, x0, y0, EMPTY, True)
                if abs(r - agent.r) + abs(c - agent.c) == 1:
                    draw_prob_overlay(surf, r, c, x0, y0, prob_map)

    draw_agent_circle(surf, agent, x0, y0, frame)

    sy = y0 + GRID * TILE + 8
    stats = [
        (f"Banked: {agent.banked_loot}", (92, 235, 145)),
        (f"Loot: {agent.loot}", (255, 213, 96)),
        (f"Detection: {agent.detection}% [{agent.risk_level()}]", agent.risk_color()),
        (f"Resources: {agent.resources}", (125, 178, 255)),
    ]
    col_w = (GRID * TILE) // len(stats)
    for i, (text, color) in enumerate(stats):
        rshadow(surf, text, F(14, bold=True), color, x0 + i * col_w, sy)


def draw_info_panel(surf, game, px, py, pw, ph):
    draw_3d_rect(surf, (17, 20, 36), (8, 10, 18), (px, py, pw, ph), depth=6, radius=14)
    cy = py + 14

    def section(title, color):
        nonlocal cy
        pygame.draw.rect(surf, tuple(v // 3 for v in color), (px + 12, cy, pw - 24, 32), border_radius=8)
        pygame.draw.rect(surf, color, (px + 12, cy, pw - 24, 32), 1, border_radius=8)
        rshadow(surf, title, F(15, bold=True), color, px + 18, cy + 7)
        cy += 40

    def kv(label, value, color):
        nonlocal cy
        lt = F(14).render(f"{label}: ", True, (146, 150, 190))
        vt = F(14, bold=True).render(str(value), True, color)
        surf.blit(lt, (px + 16, cy))
        surf.blit(vt, (px + 16 + lt.get_width(), cy))
        cy += 22

    def bar_row(label, val, maxv, fg):
        nonlocal cy
        surf.blit(F(13).render(label, True, (130, 136, 176)), (px + 16, cy))
        cy += 16
        draw_bar(surf, px + 16, cy, pw - 32, 14, val, maxv, fg)
        cy += 22

    def powers(agent):
        nonlocal cy
        surf.blit(F(13, bold=True).render("SPECIAL POWER", True, (180, 232, 255)), (px + 16, cy))
        cy += 19
        badge_col = POWERS[POWER_CLOAK]["col"]
        state = "ACTIVE" if agent.has_power(POWER_CLOAK) else "READY" if agent.resources >= 20 else "LOCKED"
        pygame.draw.rect(surf, (23, 34, 55), (px + 16, cy, pw - 32, 54), border_radius=8)
        pygame.draw.rect(surf, badge_col, (px + 16, cy, pw - 32, 54), 1, border_radius=8)
        surf.blit(F(14, bold=True).render("CLOAK", True, badge_col), (px + 28, cy + 8))
        surf.blit(F(13).render("Cost: 20 resources | Blocks alarm and guard detection", True, (210, 220, 245)), (px + 28, cy + 28))
        tag = F(12, bold=True).render(state, True, badge_col if state != "LOCKED" else (150, 150, 170))
        surf.blit(tag, (px + pw - 32 - tag.get_width(), cy + 10))
        cy += 64

    section("SHADOW", game.player.color)
    kv("Banked loot", game.player.banked_loot, (92, 235, 145))
    kv("Current loot", game.player.loot, (255, 213, 96))
    bar_row(f"Detection {game.player.detection}/100 [{game.player.risk_level()}]", game.player.detection, 100, game.player.risk_color())
    bar_row(f"Resources {game.player.resources}/100", game.player.resources, 100, (115, 170, 255))
    powers(game.player)
    cy += 4
    pygame.draw.line(surf, (52, 58, 88), (px + 12, cy), (px + pw - 12, cy), 1)
    cy += 12

    section("PHANTOM", game.opponent.color)
    kv("Banked loot", game.opponent.banked_loot, (92, 235, 145))
    kv("Current loot", game.opponent.loot, (255, 213, 96))
    bar_row(f"Detection {game.opponent.detection}/100 [{game.opponent.risk_level()}]", game.opponent.detection, 100, game.opponent.risk_color())
    bar_row(f"Resources {game.opponent.resources}/100", game.opponent.resources, 100, (115, 170, 255))
    powers(game.opponent)
    cy += 4
    pygame.draw.line(surf, (52, 58, 88), (px + 12, cy), (px + pw - 12, cy), 1)
    cy += 12

    surf.blit(F(14, bold=True).render("RULES", True, (168, 176, 220)), (px + 16, cy))
    cy += 22
    rules = [
        "30% of tiles contain loot.",
        "40% of tiles contain an alarm or guard.",
        "Alarm and guard tiles show their detection values.",
        "Cloak is the only special power.",
        "Every 2 moves the resource bar gains +10.",
        "At 100 detection, that agent loses instantly.",
    ]
    for line in rules:
        surf.blit(F(13).render(f"- {line}", True, (204, 210, 236)), (px + 16, cy))
        cy += 18

    cy += 8
    surf.blit(F(14, bold=True).render("TILE LEGEND", True, (168, 176, 220)), (px + 16, cy))
    cy += 22
    legend = [
        (LOOT, "LOOT   adds to carried loot"),
        (ALARM, "ALARM  adds its shown detection"),
        (GUARD, "GUARD  adds its shown detection"),
        (EXIT, "EXIT   banks carried loot safely"),
    ]
    for tile, desc in legend:
        pygame.draw.rect(surf, TILE_FACE[tile], (px + 16, cy, 20, 16), border_radius=4)
        surf.blit(F(12, bold=True).render(TILE_ICON[tile], True, TILE_ACCENT[tile]), (px + 18, cy + 1))
        surf.blit(F(13).render(desc, True, TILE_ACCENT[tile]), (px + 44, cy))
        cy += 20

    cy += 8
    surf.blit(F(14, bold=True).render("ACTION LOG", True, (168, 176, 220)), (px + 16, cy))
    cy += 20
    max_lines = (ph - (cy - py) - 10) // 18
    for line in game.log[-max_lines:]:
        lower = line.lower()
        if "***" in line or "lost" in lower:
            color = (255, 112, 112)
        elif "loot" in lower or "escaped" in lower:
            color = (255, 214, 96)
        elif "cloak" in lower:
            color = (135, 235, 255)
        elif "resource" in lower:
            color = (130, 180, 255)
        elif "alarm" in lower or "guard" in lower:
            color = (255, 150, 188)
        else:
            color = (178, 184, 220)
        surf.blit(F(12).render(line[:58], True, color), (px + 16, cy))
        cy += 18
        if cy > py + ph - 10:
            break


def draw_top_bar(surf, game):
    pygame.draw.rect(surf, (13, 15, 28), (0, 0, W, 78))
    pygame.draw.line(surf, (58, 62, 94), (0, 78), (W, 78), 1)
    title = "SHADOW HEIST  -  Loot vs Alarm Grid"
    tw = F(24, bold=True).render(title, True, (0, 0, 0)).get_width()
    rshadow(surf, title, F(24, bold=True), (190, 130, 255), W // 2 - tw // 2, 14)
    rshadow(surf, f"Turn: {game.turn} / {game.max_turn}", F(16, bold=True), (205, 210, 240), 20, 18)
    hint = F(14).render("ENTER = next move    SPACE = restart", True, (180, 190, 220))
    surf.blit(hint, (W - hint.get_width() - 22, 20))
    subtitle = "Loot raises score, alarms and guards raise detection, cloak blocks the trigger."
    surf.blit(F(14).render(subtitle, True, (118, 128, 170)), (20, 48))


def draw_game_over(surf, game):
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((5, 6, 15, 220))
    surf.blit(overlay, (0, 0))
    bw, bh = 980, 190
    bx, by = W // 2 - bw // 2, H // 2 - bh // 2
    draw_3d_rect(surf, (28, 22, 62), (10, 8, 24), (bx, by, bw, bh), depth=8, radius=18)
    pygame.draw.rect(surf, (145, 104, 255), (bx, by, bw, bh), 2, border_radius=18)
    result = game.winner_text()
    ww = F(28, bold=True).render(result, True, (0, 0, 0)).get_width()
    rshadow(surf, result, F(28, bold=True), (255, 219, 96), bx + bw // 2 - ww // 2, by + 40)
    info = f"Shadow total loot: {game.player.banked_loot + game.player.loot}   |   Phantom total loot: {game.opponent.banked_loot + game.opponent.loot}"
    surf.blit(F(18).render(info, True, (214, 220, 244)), (bx + bw // 2 - F(18).render(info, True, (0, 0, 0)).get_width() // 2, by + 95))
    tip = F(17).render("Press SPACE to restart", True, (164, 170, 210))
    surf.blit(tip, (bx + bw // 2 - tip.get_width() // 2, by + bh - 46))


def draw(surf, game, frame):
    draw_background(surf, frame)
    draw_top_bar(surf, game)

    player_prob = build_prob_map(game.player_grid, game.player_visited)
    opponent_prob = build_prob_map(game.opponent_grid, game.opponent_visited)

    left_x = 24
    right_x = left_x + GRID * TILE + 52
    panel_x = right_x + GRID * TILE + 24
    panel_w = W - panel_x - 16
    grid_y = 110

    draw_grid_view(
        surf,
        game,
        game.player,
        game.player_grid,
        game.player_visited,
        game.player_reveal,
        left_x,
        grid_y,
        "SHADOW'S VIEW",
        player_prob,
        frame,
    )
    draw_grid_view(
        surf,
        game,
        game.opponent,
        game.opponent_grid,
        game.opponent_visited,
        game.opponent_reveal,
        right_x,
        grid_y,
        "PHANTOM'S VIEW",
        opponent_prob,
        frame,
    )
    draw_info_panel(surf, game, panel_x, 98, panel_w, H - 114)

    if game.over:
        draw_game_over(surf, game)


# ============================================================
# MAIN
# ============================================================
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Shadow Heist - Loot vs Alarm")
    clock = pygame.time.Clock()
    game = Game()
    next_to_move = 0
    frame = 0

    while True:
        clock.tick(FPS)
        frame += 1

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_SPACE:
                    game = Game()
                    next_to_move = 0
                elif ev.key == pygame.K_RETURN and not game.over:
                    if next_to_move == 0:
                        shadow_turn(game)
                    else:
                        phantom_turn(game)
                    game.turn += 1
                    if game.is_over():
                        game.over = True
                    next_to_move = 1 - next_to_move

        game.player.tick_visuals()
        game.opponent.tick_visuals()
        draw(screen, game, frame)
        pygame.display.flip()


if __name__ == "__main__":
    main()
import pygame, sys, random, heapq, math

# ============================================================
# CONFIG
# ============================================================
GRID      = 8
TILE      = 84
W, H      = 1900, 1080
FPS       = 60

EMPTY, VAULT, CAMERA, DATA, EXIT, ALARM = range(6)

TILE_FACE = {
    EMPTY:  (32,  34,  58),
    VAULT:  (210, 155,  20),
    CAMERA: (200,  50,  50),
    DATA:   ( 20, 160, 220),
    EXIT:   ( 40, 200, 100),
    ALARM:  (190,  50, 200),
}
TILE_SHADOW = {
    EMPTY:  (18, 19, 35),
    VAULT:  (120, 88,  8),
    CAMERA: (110, 20, 20),
    DATA:   ( 10, 80, 120),
    EXIT:   ( 18, 100, 50),
    ALARM:  ( 95, 20, 105),
}
TILE_ACCENT = {
    EMPTY:  (80,  85, 130),
    VAULT:  (255, 220, 100),
    CAMERA: (255, 120, 120),
    DATA:   (120, 220, 255),
    EXIT:   (120, 255, 160),
    ALARM:  (240, 130, 255),
}
TILE_LABEL = {
    EMPTY: "", VAULT: "VAULT", CAMERA: "CAMERA",
    DATA: "DATA", EXIT: "EXIT", ALARM: "ALARM",
}
TILE_ICON = {
    EMPTY: "", VAULT: "[V]", CAMERA: "[C]",
    DATA: "[D]", EXIT: "[X]", ALARM: "[!]",
}

POWER_VISIBILITY = "visibility"
POWER_CLOAKING   = "cloaking"
POWER_TELEPORT   = "teleport"
POWER_SCRAMBLE   = "scramble"

POWERS = {
    POWER_VISIBILITY: {"cost": 30, "name": "REVEAL",   "duration": 3, "col": (100, 200, 255)},
    POWER_CLOAKING:   {"cost": 25, "name": "CLOAK",    "duration": 2, "col": (180, 130, 255)},
    POWER_TELEPORT:   {"cost": 40, "name": "TELEPORT", "duration": 0, "col": (255, 220,  80)},
    POWER_SCRAMBLE:   {"cost": 35, "name": "SCRAMBLE", "duration": 1, "col": (255, 130,  60)},
}

# ============================================================
# FONT CACHE
# ============================================================
_FONTS = {}
def F(size, bold=False):
    k = (size, bold)
    if k not in _FONTS:
        _FONTS[k] = pygame.font.SysFont("Arial", size, bold=bold)
    return _FONTS[k]

# ============================================================
# DRAW HELPERS
# ============================================================
def draw_3d_rect(surf, face, shadow, rect, depth=5, radius=6):
    x, y, w, h = rect
    pygame.draw.rect(surf, shadow, (x+depth, y+depth, w, h), border_radius=radius)
    pygame.draw.rect(surf, face,   (x, y, w, h),             border_radius=radius)
    hl = tuple(min(255, c+60) for c in face)
    pygame.draw.line(surf, hl, (x+radius, y+1), (x+w-radius, y+1))
    pygame.draw.line(surf, hl, (x+1, y+radius), (x+1, y+h-radius))

def draw_bar(surf, x, y, w, h, val, maxv, fg, bg=(25,27,48), radius=4):
    pygame.draw.rect(surf, bg,  (x, y, w, h), border_radius=radius)
    filled = max(0, int(w * min(val, maxv) / maxv))
    if filled:
        pygame.draw.rect(surf, fg, (x, y, filled, h), border_radius=radius)
        shine = tuple(min(255, c+80) for c in fg)
        stripe_h = max(2, h//3)
        pygame.draw.rect(surf, shine, (x, y, filled, stripe_h), border_radius=radius)
    pygame.draw.rect(surf, (60,65,100), (x, y, w, h), 1, border_radius=radius)

def rshadow(surf, txt, fnt, col, x, y, sc=(0,0,0), off=2):
    surf.blit(fnt.render(txt, True, sc), (x+off, y+off))
    surf.blit(fnt.render(txt, True, col), (x, y))

def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

# ============================================================
# AGENT
# ============================================================
class Agent:
    def __init__(self, name, color, pos):
        self.name      = name
        self.color     = color
        self.r, self.c = pos
        self.score     = 0
        self.secured   = 0
        self.detection = 0
        self.alive     = True
        self.resources = 0
        self.active_powers   = {}
        self.last_action     = ""
        self.last_pos        = None
        self.power_flash     = 0
        self.power_flash_col = (255,255,255)
        self.power_name_disp = ""

    def pos(self): return (self.r, self.c)

    def risk_level(self):
        if self.detection >= 80: return "CRITICAL"
        if self.detection >= 60: return "HIGH"
        if self.detection >= 40: return "MEDIUM"
        if self.detection >= 20: return "LOW"
        return "SAFE"

    def risk_color(self):
        t = self.detection / 100
        if t < 0.4:  return lerp_col((60,220,140), (255,220,60), t/0.4)
        return       lerp_col((255,220,60), (255,50,50), (t-0.4)/0.6)

    def has_power(self, p):
        return p in self.active_powers and self.active_powers[p] > 0

    def activate_power(self, p):
        cost = POWERS[p]["cost"]
        if self.resources >= cost:
            self.resources -= cost          # deduct immediately
            dur = POWERS[p]["duration"]
            if dur > 0:
                self.active_powers[p] = dur
            self.power_flash     = 50
            self.power_flash_col = POWERS[p]["col"]
            self.power_name_disp = POWERS[p]["name"]
            return True
        return False

    def update_powers(self):
        for p in list(self.active_powers):
            self.active_powers[p] -= 1
            if self.active_powers[p] <= 0:
                del self.active_powers[p]

    def tick_flash(self):
        if self.power_flash > 0:
            self.power_flash -= 1

# ============================================================
# PER-CELL PROBABILITY MAP
# ============================================================
def build_prob_map(grid, visited):
    remaining = {VAULT:0, DATA:0, CAMERA:0, ALARM:0}
    hidden = 0
    for r in range(GRID):
        for c in range(GRID):
            if not visited[r][c]:
                hidden += 1
                t = grid[r][c]
                if t in remaining:
                    remaining[t] += 1

    prob = [[None]*GRID for _ in range(GRID)]
    for r in range(GRID):
        for c in range(GRID):
            if visited[r][c] or hidden == 0:
                prob[r][c] = {k:0.0 for k in (VAULT,DATA,CAMERA,ALARM)}
            else:
                # Each hidden cell gets its OWN probability
                # P(this cell = T) = remaining[T] / hidden_count
                # This correctly differs per cell because every cell draws from the same pool
                # but we show the marginal probability for that specific cell.
                prob[r][c] = {
                    VAULT:  remaining[VAULT]  / hidden,
                    DATA:   remaining[DATA]   / hidden,
                    CAMERA: remaining[CAMERA] / hidden,
                    ALARM:  remaining[ALARM]  / hidden,
                }
    return prob

# ============================================================
# GAME
# ============================================================
class Game:
    def __init__(self):
        self.turn     = 0
        self.max_turn = 60
        self.over     = False
        self.log      = []

        self.player_grid     = [[EMPTY]*GRID for _ in range(GRID)]
        self.opponent_grid   = [[EMPTY]*GRID for _ in range(GRID)]
        self.player_visited  = [[False]*GRID for _ in range(GRID)]
        self.opponent_visited= [[False]*GRID for _ in range(GRID)]
        self.player_reveal   = [[None]*GRID  for _ in range(GRID)]
        self.opponent_reveal = [[None]*GRID  for _ in range(GRID)]

        self.player_moves    = 0
        self.opponent_moves  = 0

        cells = [(r,c) for r in range(GRID) for c in range(GRID)]
        random.shuffle(cells)
        idx=0
        self.vaults     = cells[idx:idx+4];  idx+=4
        self.data_tiles = cells[idx:idx+12]; idx+=12
        self.cameras    = cells[idx:idx+6];  idx+=6
        self.alarms     = cells[idx:idx+5];  idx+=5

        for g in [self.player_grid, self.opponent_grid]:
            for r,c in self.vaults:     g[r][c]=VAULT
            for r,c in self.data_tiles: g[r][c]=DATA
            for r,c in self.cameras:    g[r][c]=CAMERA
            for r,c in self.alarms:     g[r][c]=ALARM

        self.exitA = self._edge([])
        self.exitB = self._edge([self.exitA])
        self.player_grid[self.exitA[0]][self.exitA[1]]   = EXIT
        self.opponent_grid[self.exitB[0]][self.exitB[1]] = EXIT

        ps = self._edge([self.exitA])
        os = self._edge([self.exitA, self.exitB, ps])

        self.player   = Agent("Shadow",  (100,200,255), ps)
        self.opponent = Agent("Phantom", (255,140, 80), os)

        for pos, vis, rev, g in [
            (ps,  self.player_visited,   self.player_reveal,   self.player_grid),
            (self.exitA, self.player_visited,   self.player_reveal,   self.player_grid),
            (os,  self.opponent_visited, self.opponent_reveal, self.opponent_grid),
            (self.exitB, self.opponent_visited, self.opponent_reveal, self.opponent_grid),
        ]:
            r,c = pos
            vis[r][c] = True
            if rev[r][c] is None: rev[r][c] = g[r][c]

    def _edge(self, exclude):
        edges = list(set(
            [(0,c) for c in range(GRID)] + [(GRID-1,c) for c in range(GRID)] +
            [(r,0) for r in range(GRID)] + [(r,GRID-1) for r in range(GRID)]
        ))
        edges = [e for e in edges if e not in exclude]
        return random.choice(edges)

    def neighbors(self, r, c):
        for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]:
            nr,nc = r+dr, c+dc
            if 0 <= nr < GRID and 0 <= nc < GRID:
                yield nr, nc

    def apply_tile(self, agent, grid, visited, reveal, old_r, old_c):
        r, c = agent.r, agent.c
        tile = grid[r][c]
        if visited: visited[r][c] = True
        if reveal and reveal[r][c] is None: reveal[r][c] = tile

        if tile == DATA:
            agent.score += 20
            grid[r][c] = EMPTY
            agent.last_action = "Collected DATA (+20 pts)"
            self.log.append(f"{agent.name}: {agent.last_action}")

        elif tile == VAULT:
            agent.score += 50
            agent.detection = min(100, agent.detection+15)
            grid[r][c] = EMPTY
            agent.last_action = "Hacked VAULT! (+50 pts, +15 det)"
            self.log.append(f"{agent.name}: {agent.last_action}")

        elif tile == CAMERA:
            add = 10 if not agent.has_power(POWER_CLOAKING) else 0
            agent.detection = min(100, agent.detection+add)
            blk = "[BLOCKED by CLOAK]" if add==0 else f"+{add} det"
            agent.last_action = f"Hit CAMERA ({blk})"
            self.log.append(f"{agent.name}: {agent.last_action}")

        elif tile == ALARM:
            add = 25 if not agent.has_power(POWER_CLOAKING) else 0
            agent.detection = min(100, agent.detection+add)
            grid[r][c] = EMPTY
            blk = "[BLOCKED by CLOAK]" if add==0 else f"+{add} det"
            agent.last_action = f"Triggered ALARM! ({blk})"
            self.log.append(f"{agent.name}: {agent.last_action}")

        elif tile == EXIT:
            if agent.score > 0:
                banked = agent.score
                agent.secured += banked
                agent.last_action = f"ESCAPED! Banked {banked} pts (Total: {agent.secured})"
                self.log.append(f"{agent.name}: {agent.last_action}")
            agent.score = 0

        if agent.detection >= 100:
            agent.alive = False
            self.log.append(f"*** {agent.name} ELIMINATED! Detection maxed! ***")

    def move_agent(self, agent, grid, visited, reveal, nr, nc, is_player):
        agent.last_pos = (agent.r, agent.c)
        agent.r, agent.c = nr, nc
        self.apply_tile(agent, grid, visited, reveal, agent.last_pos[0], agent.last_pos[1])
        if not agent.has_power(POWER_CLOAKING):
            agent.detection = min(100, agent.detection+2)
        agent.update_powers()
        if is_player:
            self.player_moves += 1
            if self.player_moves % 4 == 0:
                agent.resources = min(100, agent.resources+10)
                self.log.append(f"{agent.name}: +10 resources -> {agent.resources}")
        else:
            self.opponent_moves += 1
            if self.opponent_moves % 4 == 0:
                agent.resources = min(100, agent.resources+10)
                self.log.append(f"{agent.name}: +10 resources -> {agent.resources}")

    def is_over(self):
        return self.turn >= self.max_turn or not self.player.alive or not self.opponent.alive

    def winner_text(self):
        if not self.player.alive and not self.opponent.alive: return "TIE -- Both eliminated"
        if not self.player.alive:
            return f"PHANTOM WINS ({self.opponent.secured} pts) -- Shadow eliminated"
        if not self.opponent.alive:
            return f"SHADOW WINS ({self.player.secured} pts) -- Phantom eliminated"
        p = self.player.secured + self.player.score
        o = self.opponent.secured + self.opponent.score
        if p > o: return f"SHADOW WINS!  {p} vs {o} pts"
        if o > p: return f"PHANTOM WINS!  {o} vs {p} pts"
        return f"TIE -- Both scored {p} pts"

# ============================================================
# AI: MINIMAX (Shadow)
# ============================================================
def eval_state(game, agent, visited):
    s = agent.secured + agent.score
    return (s - agent.detection*2 + agent.resources*0.5
            + (100 if agent.alive else -1000)
            + (150 if visited and not visited[agent.r][agent.c] else 0))

def minimax(game, agent, depth, maxi, alpha, beta, grid, visited):
    if depth == 0 or not agent.alive:
        return eval_state(game, agent, visited), None
    nb = list(game.neighbors(agent.r, agent.c))
    if not nb: return eval_state(game, agent, visited), None

    def pri(pos):
        r,c = pos
        if not visited[r][c] and grid[r][c] in (VAULT,DATA): return 0
        if not visited[r][c]: return 1
        if grid[r][c] == EXIT: return 2
        return 3
    nb.sort(key=pri)

    bv = -1e9 if maxi else 1e9
    bm = None
    for nr,nc in nb:
        sv = (agent.r,agent.c,agent.detection,agent.score,agent.secured,
              agent.resources,agent.active_powers.copy(),
              [row[:] for row in grid],[row[:] for row in visited])
        agent.r,agent.c = nr,nc
        if visited: visited[nr][nc] = True
        game.apply_tile(agent,grid,None,None,sv[0],sv[1])
        v,_ = minimax(game,agent,depth-1,not maxi,alpha,beta,grid,visited)
        agent.r,agent.c = sv[0],sv[1]
        agent.detection,agent.score,agent.secured = sv[2],sv[3],sv[4]
        agent.resources,agent.active_powers = sv[5],sv[6]
        grid[:] = sv[7]; visited[:] = sv[8]
        if maxi:
            if v > bv: bv,bm = v,(nr,nc)
            alpha = max(alpha, v)
        else:
            if v < bv: bv,bm = v,(nr,nc)
            beta = min(beta, v)
        if beta <= alpha: break
    return bv, bm

def shadow_turn(game):
    a = game.player
    if a.resources >= POWERS[POWER_VISIBILITY]["cost"] and random.random() < 0.18 and not a.has_power(POWER_VISIBILITY):
        if a.activate_power(POWER_VISIBILITY):
            game.log.append(f"{a.name}: Used REVEAL power! (cost 30 res)")
            for nr,nc in game.neighbors(a.r,a.c):
                game.player_visited[nr][nc] = True
                if game.player_reveal[nr][nc] is None:
                    game.player_reveal[nr][nc] = game.player_grid[nr][nc]
    if a.detection > 50 and a.resources >= POWERS[POWER_CLOAKING]["cost"] and not a.has_power(POWER_CLOAKING):
        if a.activate_power(POWER_CLOAKING):
            game.log.append(f"{a.name}: Used CLOAK power! (cost 25 res)")

    unexp = [(r,c) for r,c in game.neighbors(a.r,a.c) if not game.player_visited[r][c]]
    if unexp:
        unexp.sort(key=lambda p: {VAULT:0,DATA:1}.get(game.player_grid[p[0]][p[1]],2))
        best = unexp[0]
    else:
        _,best = minimax(game,a,3,True,-1e9,1e9,game.player_grid,game.player_visited)

    if best and a.last_pos and best == a.last_pos:
        alts = [m for m in game.neighbors(a.r,a.c) if m != a.last_pos]
        if alts: best = random.choice(alts)

    if best:
        game.move_agent(a,game.player_grid,game.player_visited,
                        game.player_reveal,best[0],best[1],True)
    a.tick_flash()

# ============================================================
# AI: A* (Phantom)
# ============================================================
def astar(game, start, goals, grid):
    if not goals: return None
    open_set = [(0, start)]
    came = {}; g = {start:0}
    goal = None
    while open_set:
        _,cur = heapq.heappop(open_set)
        if cur in goals: goal = cur; break
        for nxt in game.neighbors(*cur):
            t = g[cur]+1
            if nxt not in g or t < g[nxt]:
                g[nxt] = t
                heapq.heappush(open_set,(t+min(abs(nxt[0]-gl[0])+abs(nxt[1]-gl[1]) for gl in goals),nxt))
                came[nxt] = cur
    if goal is None or goal == start:
        nb = list(game.neighbors(*start))
        return random.choice(nb) if nb else None
    cur = goal
    while came.get(cur) != start:
        if cur not in came:
            nb = list(game.neighbors(*start)); return random.choice(nb) if nb else None
        cur = came[cur]
    return cur

def phantom_turn(game):
    a = game.opponent
    if a.resources >= POWERS[POWER_VISIBILITY]["cost"] and random.random() < 0.20 and not a.has_power(POWER_VISIBILITY):
        if a.activate_power(POWER_VISIBILITY):
            game.log.append(f"{a.name}: Used REVEAL power! (cost 30 res)")
            for nr,nc in game.neighbors(a.r,a.c):
                game.opponent_visited[nr][nc] = True
                if game.opponent_reveal[nr][nc] is None:
                    game.opponent_reveal[nr][nc] = game.opponent_grid[nr][nc]
    if a.detection > 50 and a.resources >= POWERS[POWER_CLOAKING]["cost"] and not a.has_power(POWER_CLOAKING):
        if a.activate_power(POWER_CLOAKING):
            game.log.append(f"{a.name}: Used CLOAK power! (cost 25 res)")

    unexp = [p for p in game.neighbors(a.r,a.c) if not game.opponent_visited[p[0]][p[1]]]
    if unexp:
        nr,nc = random.choice(unexp)
        game.move_agent(a,game.opponent_grid,game.opponent_visited,
                        game.opponent_reveal,nr,nc,False)
        a.tick_flash(); return

    def go(goals):
        m = astar(game,a.pos(),goals,game.opponent_grid)
        if m:
            game.move_agent(a,game.opponent_grid,game.opponent_visited,
                            game.opponent_reveal,m[0],m[1],False)
            return True
        return False

    if (a.r,a.c)==game.exitB and a.score>0:
        go([game.exitB]); a.tick_flash(); return
    if a.detection>70 and go([game.exitB]):    a.tick_flash(); return
    if a.detection>40 and go(game.data_tiles): a.tick_flash(); return
    if game.vaults and go(game.vaults):        a.tick_flash(); return
    if go(game.data_tiles):                    a.tick_flash(); return
    nb = list(game.neighbors(a.r,a.c))
    if nb:
        nr,nc = random.choice(nb)
        game.move_agent(a,game.opponent_grid,game.opponent_visited,
                        game.opponent_reveal,nr,nc,False)
    a.tick_flash()

# ============================================================
# RENDER
# ============================================================
DEPTH = 4

def draw_tile_3d(surf, r, c, x0, y0, tile_type,
                 is_hidden=False, collected=False):
    x = x0 + c*TILE
    y = y0 + r*TILE
    pad = 3
    rx,ry,rw,rh = x+pad, y+pad, TILE-pad*2, TILE-pad*2

    if is_hidden:
        face   = (32, 34, 60)
        shadow = (16, 17, 32)
    elif collected:
        face   = tuple(max(0,v-80) for v in TILE_FACE[tile_type])
        shadow = tuple(max(0,v-40) for v in TILE_SHADOW[tile_type])
    else:
        face   = TILE_FACE[tile_type]
        shadow = TILE_SHADOW[tile_type]

    for i in range(DEPTH, 0, -1):
        shade = tuple(max(0,int(shadow[j]*(1-i*0.15))) for j in range(3))
        pygame.draw.rect(surf, shade, (rx+i, ry+i, rw, rh), border_radius=5)
    pygame.draw.rect(surf, face, (rx, ry, rw, rh), border_radius=5)

    if not is_hidden:
        hl = tuple(min(255, v+70) for v in face)
        pygame.draw.line(surf, hl, (rx+5, ry+1), (rx+rw-5, ry+1))
        pygame.draw.line(surf, hl, (rx+1, ry+5), (rx+1, ry+rh-5))
        dk = tuple(max(0, v-40) for v in face)
        pygame.draw.line(surf, dk, (rx+5, ry+rh-1), (rx+rw-5, ry+rh-1))
        pygame.draw.line(surf, dk, (rx+rw-1, ry+5), (rx+rw-1, ry+rh-5))

    if is_hidden:
        fnt = F(24, bold=True)
        qs = fnt.render("?", True, (50,55,90))
        surf.blit(qs, (rx+rw//2-qs.get_width()//2+2, ry+rh//2-qs.get_height()//2+2))
        q = fnt.render("?", True, (80,85,135))
        surf.blit(q, (rx+rw//2-q.get_width()//2, ry+rh//2-q.get_height()//2))
    else:
        icon = TILE_ICON.get(tile_type, "")
        lbl  = TILE_LABEL.get(tile_type, "")
        if icon:
            ac = TILE_ACCENT.get(tile_type, (200,200,200))
            if collected: ac = tuple(max(0,v-80) for v in ac)
            it = F(16, bold=True).render(icon, True, ac)
            surf.blit(it, (rx+rw//2-it.get_width()//2, ry+8))
        if lbl:
            ac = TILE_ACCENT.get(tile_type, (200,200,200))
            if collected: ac = tuple(max(0,v-80) for v in ac); lbl += " done"
            lt = F(12, bold=True).render(lbl, True, ac)
            surf.blit(lt, (rx+rw//2-lt.get_width()//2, ry+rh-20))

def draw_prob_overlay(surf, r, c, x0, y0, prob_map):
    x = x0 + c*TILE + 3
    y = y0 + r*TILE + 3
    rw = TILE - 6
    rh = TILE - 6
    p = prob_map[r][c]
    lines = [
        (f"V:{int(p[VAULT]*100)}%",  (230,190, 60)),
        (f"D:{int(p[DATA]*100)}%",   ( 80,200,240)),
        (f"C:{int(p[CAMERA]*100)}%", (230, 80, 80)),
        (f"A:{int(p[ALARM]*100)}%",  (220, 80,220)),
    ]
    fnt = F(12, bold=True)
    line_h = 15
    total_h = len(lines)*line_h
    sy = y + rh//2 - total_h//2
    for i,(txt,col) in enumerate(lines):
        rshadow(surf, txt, fnt, col, x+rw//2-fnt.render(txt,True,(0,0,0)).get_width()//2,
                sy + i*line_h)

def draw_agent_circle(surf, agent, x0, y0, frame):
    cx = x0 + agent.c*TILE + TILE//2
    cy = y0 + agent.r*TILE + TILE//2

    if agent.active_powers:
        pk = list(agent.active_powers.keys())[0]
        ac = POWERS[pk]["col"]
        pulse = int(15 + 8*math.sin(frame*0.15))
        aura = pygame.Surface((pulse*2+50, pulse*2+50), pygame.SRCALPHA)
        pygame.draw.circle(aura, (*ac,55), (pulse+25,pulse+25), pulse+20)
        surf.blit(aura, (cx-pulse-25, cy-pulse-25))

    if agent.power_flash > 0:
        frac = agent.power_flash/50
        ring_r = int(20+20*frac)
        rc = agent.power_flash_col
        rs = pygame.Surface((ring_r*2+4, ring_r*2+4), pygame.SRCALPHA)
        pygame.draw.circle(rs, (*rc,int(220*frac)), (ring_r+2,ring_r+2), ring_r, 3)
        surf.blit(rs, (cx-ring_r-2, cy-ring_r-2))
        if frac > 0.25:
            pw_fnt = F(15, bold=True)
            rshadow(surf, agent.power_name_disp, pw_fnt, rc,
                    cx - pw_fnt.render(agent.power_name_disp,True,(0,0,0)).get_width()//2,
                    cy - 44)

    pygame.draw.circle(surf, (0,0,0), (cx+3, cy+3), 20)
    dark = tuple(max(0,v-70) for v in agent.color)
    pygame.draw.circle(surf, dark, (cx, cy), 21)
    pygame.draw.circle(surf, agent.color, (cx, cy), 18)
    hl = tuple(min(255,v+110) for v in agent.color)
    pygame.draw.circle(surf, hl, (cx-5, cy-6), 7)
    pygame.draw.circle(surf, (255,255,255), (cx, cy), 18, 2)
    init = F(15, bold=True).render(agent.name[0], True, (8,8,18))
    surf.blit(init, (cx-init.get_width()//2, cy-init.get_height()//2))

def draw_grid_view(surf, game, agent, grid, visited, reveal,
                   x0, y0, label_str, prob_map, frame):
    pw = GRID*TILE + 18
    ph = GRID*TILE + 18
    draw_3d_rect(surf, (22,24,45), (10,12,24), (x0-9,y0-9,pw,ph), depth=7, radius=10)

    pygame.draw.rect(surf, (18,20,38), (x0-9,y0-40,pw,34), border_radius=8)
    pygame.draw.rect(surf, agent.color, (x0-9,y0-40,pw,34), 2, border_radius=8)
    ls = F(16, bold=True)
    lw = ls.render(label_str,True,(0,0,0)).get_width()
    rshadow(surf, label_str, ls, agent.color, x0+pw//2-lw//2-9, y0-35)

    for r in range(GRID):
        for c in range(GRID):
            orig = reveal[r][c]
            cur  = grid[r][c]
            vis  = visited[r][c]
            if vis:
                tile  = orig if orig is not None else cur
                coll  = (cur == EMPTY and tile not in (EMPTY, EXIT, CAMERA))
                draw_tile_3d(surf,r,c,x0,y0,tile,is_hidden=False,collected=coll)
            else:
                draw_tile_3d(surf,r,c,x0,y0,EMPTY,is_hidden=True)
                if (abs(r-agent.r)+abs(c-agent.c)) == 1:
                    draw_prob_overlay(surf,r,c,x0,y0,prob_map)

    draw_agent_circle(surf, agent, x0, y0, frame)

    sy = y0 + GRID*TILE + 6
    stats = [
        (f"Secured: {agent.secured}", (80,220,130)),
        (f"Carried: {agent.score}",   (255,200,80)),
        (f"Detect: {agent.detection}%  [{agent.risk_level()}]", agent.risk_color()),
        (f"Res: {agent.resources}",   (120,160,255)),
    ]
    col_w = (GRID*TILE) // len(stats)
    for i,(txt,col) in enumerate(stats):
        rshadow(surf, txt, F(14,bold=True), col, x0+i*col_w, sy)

def draw_info_panel(surf, game, px, py, pw, ph):
    draw_3d_rect(surf,(18,20,38),(8,9,18),(px,py,pw,ph),depth=5,radius=12)

    cy = py + 12

    def section_hdr(title, col):
        nonlocal cy
        pygame.draw.rect(surf, tuple(v//3 for v in col), (px+10,cy,pw-20,30), border_radius=7)
        pygame.draw.rect(surf, col, (px+10,cy,pw-20,30), 1, border_radius=7)
        rshadow(surf, title, F(15,bold=True), col, px+16, cy+6)
        cy += 36

    def kv(lbl, val, vc):
        nonlocal cy
        lt = F(14).render(lbl+"  ", True, (140,145,185))
        vt = F(14,bold=True).render(str(val), True, vc)
        surf.blit(lt, (px+14, cy))
        surf.blit(vt, (px+14+lt.get_width(), cy))
        cy += 21

    def bar_row(lbl, val, maxv, fg):
        nonlocal cy
        surf.blit(F(13).render(lbl, True, (130,135,175)), (px+14,cy))
        cy += 16
        draw_bar(surf, px+14, cy, pw-28, 13, val, maxv, fg)
        cy += 19

    def power_section(agent):
        nonlocal cy
        surf.blit(F(13,bold=True).render("ACTIVE POWERS:", True, (200,180,255)), (px+14,cy))
        cy += 18
        if agent.active_powers:
            for p,turns in agent.active_powers.items():
                pc = POWERS[p]["col"]
                pn = POWERS[p]["name"]
                pygame.draw.rect(surf, tuple(v//4 for v in pc), (px+14,cy,pw-28,22), border_radius=5)
                pygame.draw.rect(surf, pc, (px+14,cy,pw-28,22), 1, border_radius=5)
                pt = F(13,bold=True).render(f"  {pn}  ({turns} turns left)", True, pc)
                surf.blit(pt, (px+16, cy+3))
                cy += 26
        else:
            surf.blit(F(13).render("  None", True, (70,75,110)), (px+14,cy))
            cy += 21

    # SHADOW block
    section_hdr("  SHADOW  (Minimax AI)", game.player.color)
    kv("Secured pts", game.player.secured, (80,220,130))
    kv("Carried pts", game.player.score,   (255,200,80))
    bar_row(f"Detection  {game.player.detection}/100  [{game.player.risk_level()}]",
            game.player.detection, 100, game.player.risk_color())
    bar_row(f"Resources  {game.player.resources}/100",
            game.player.resources, 100, (100,150,255))
    power_section(game.player)
    cy += 6

    pygame.draw.line(surf,(50,54,85),(px+10,cy),(px+pw-10,cy),1)
    cy += 10

    # PHANTOM block
    section_hdr("  PHANTOM  (A* AI)", game.opponent.color)
    kv("Secured pts", game.opponent.secured, (80,220,130))
    kv("Carried pts", game.opponent.score,   (255,200,80))
    bar_row(f"Detection  {game.opponent.detection}/100  [{game.opponent.risk_level()}]",
            game.opponent.detection, 100, game.opponent.risk_color())
    bar_row(f"Resources  {game.opponent.resources}/100",
            game.opponent.resources, 100, (100,150,255))
    power_section(game.opponent)
    cy += 6

    pygame.draw.line(surf,(50,54,85),(px+10,cy),(px+pw-10,cy),1)
    cy += 10

    # Tile legend
    surf.blit(F(14,bold=True).render("TILE LEGEND", True, (160,165,210)),(px+14,cy)); cy+=20
    for tile,desc in [
        (VAULT,  "VAULT   +50 pts  +15 det"),
        (DATA,   "DATA    +20 pts"),
        (CAMERA, "CAMERA  +10 det"),
        (ALARM,  "ALARM   +25 det"),
        (EXIT,   "EXIT    bank loot safely"),
    ]:
        col = TILE_ACCENT[tile]
        pygame.draw.rect(surf, TILE_FACE[tile], (px+14,cy,18,16), border_radius=3)
        surf.blit(F(12,bold=True).render(TILE_ICON[tile], True, col), (px+16,cy+1))
        surf.blit(F(13).render("  "+desc, True, col), (px+36,cy+1))
        cy += 20
    cy += 6

    pygame.draw.line(surf,(50,54,85),(px+10,cy),(px+pw-10,cy),1)
    cy += 8

    # Action log
    surf.blit(F(14,bold=True).render("ACTION LOG", True, (160,165,210)),(px+14,cy)); cy+=18
    max_lines = (ph-(cy-py)-8)//18
    for line in game.log[-max_lines:]:
        col = (255,100,100)  if ("ELIM" in line or "***" in line) \
         else (80,220,130)   if ("Escaped" in line or "Banked" in line or "secured" in line) \
         else (255,200,80)   if ("VAULT" in line or "DATA" in line) \
         else (180,130,255)  if ("power" in line.lower() or "Used" in line) \
         else (160,180,120)  if "resources" in line \
         else (170,175,215)
        surf.blit(F(12).render(line[:54], True, col), (px+14,cy))
        cy += 18
        if cy > py+ph-10: break

def draw_top_bar(surf, game):
    pygame.draw.rect(surf,(14,15,28),(0,0,W,56))
    pygame.draw.line(surf,(55,58,92),(0,56),(W,56),1)
    title = "SHADOW HEIST  --  Minimax vs A*"
    tw = F(22,bold=True).render(title,True,(0,0,0)).get_width()
    rshadow(surf,title,F(22,bold=True),(170,90,255),W//2-tw//2,13)
    rshadow(surf,f"Turn: {game.turn} / {game.max_turn}",F(16,bold=True),(200,205,240),20,18)
    hint = F(13).render("ENTER = next move    SPACE = restart", True, (70,75,110))
    surf.blit(hint,(W-hint.get_width()-18,20))

def draw_game_over(surf, game):
    ov = pygame.Surface((W,H),pygame.SRCALPHA)
    ov.fill((5,5,15,215))
    surf.blit(ov,(0,0))
    bw,bh = 960,180
    bx,by = W//2-bw//2, H//2-bh//2
    draw_3d_rect(surf,(28,20,60),(10,8,24),(bx,by,bw,bh),depth=8,radius=18)
    pygame.draw.rect(surf,(130,80,255),(bx,by,bw,bh),2,border_radius=18)
    wt = game.winner_text()
    ww = F(28,bold=True).render(wt,True,(0,0,0)).get_width()
    rshadow(surf,wt,F(28,bold=True),(255,210,80),bx+bw//2-ww//2,by+38)
    rs = F(17).render("Press SPACE to restart",True,(160,165,210))
    surf.blit(rs,(bx+bw//2-rs.get_width()//2,by+bh-44))

def draw(surf, game, frame):
    surf.fill((9,10,20))
    draw_top_bar(surf,game)

    p_prob = build_prob_map(game.player_grid,   game.player_visited)
    o_prob = build_prob_map(game.opponent_grid,  game.opponent_visited)

    left_x  = 28
    right_x = left_x + GRID*TILE + 82
    panel_x = right_x + GRID*TILE + 38
    panel_w = W - panel_x - 16
    grid_y  = 70

    draw_grid_view(surf,game,game.player,   game.player_grid,
                   game.player_visited,  game.player_reveal,
                   left_x,  grid_y, "SHADOW'S VIEW",  p_prob, frame)
    draw_grid_view(surf,game,game.opponent, game.opponent_grid,
                   game.opponent_visited, game.opponent_reveal,
                   right_x, grid_y, "PHANTOM'S VIEW", o_prob, frame)
    draw_info_panel(surf,game,panel_x,60,panel_w,H-70)

    if game.over:
        draw_game_over(surf,game)

# ============================================================
# MAIN
# ============================================================
def main():
    pygame.init()
    screen = pygame.display.set_mode((W,H))
    pygame.display.set_caption("Shadow Heist -- Minimax vs A*")
    clock = pygame.time.Clock()
    game  = Game()
    next_to_move = 0
    frame = 0

    while True:
        clock.tick(FPS)
        frame += 1
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_SPACE and game.over:
                    game = Game(); next_to_move = 0
                elif ev.key == pygame.K_RETURN and not game.over:
                    if next_to_move == 0: shadow_turn(game)
                    else:                 phantom_turn(game)
                    game.turn += 1
                    if game.is_over(): game.over = True
                    next_to_move = 1 - next_to_move

        game.player.tick_flash()
        game.opponent.tick_flash()
        draw(screen,game,frame)
        pygame.display.flip()

if __name__ == "__main__":
    main()