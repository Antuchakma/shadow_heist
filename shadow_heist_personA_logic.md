# Shadow Heist — Person A: Game Logic & AI (Agent Spec)

---

## Your Role

You are building the **entire game engine** for Shadow Heist — a turn-based stealth strategy game on an 8×8 grid. You write **pure Python, no pygame**. Your code must be fully testable via print statements.

Person B (the renderer) will import your code and call your functions. Your job is to make the game *work*. Their job is to make it *look good*.

---

## Tech Stack

- Language: **Python 3.10+**
- No external libraries except Python's built-in `random` and `copy`
- No pygame — that is Person B's responsibility
- File structure:

```
shadow_heist/
    game/
        __init__.py
        board.py        ← tile types, board generation
        state.py        ← GameState class (the shared object)
        actions.py      ← all action logic
        detection.py    ← detection system
        fog.py          ← fog of war logic
        ai.py           ← Specter AI
        engine.py       ← turn controller, win/loss
    main.py             ← entry point (print-based test runner)
```

---

## The GameState Object (state.py)

This is the **single shared object** Person B will read from to render the game. Every piece of game data lives here. Never hide state outside of this object.

```python
@dataclass
class GameState:
    # Board
    board: list[list[Tile]]        # 8x8 grid

    # Players
    phantom_pos: tuple[int, int]   # (row, col)
    specter_pos: tuple[int, int]

    phantom_rp: int                # Resource Points
    specter_rp: int

    phantom_detection: int         # 0-100
    specter_detection: int

    # Hack tracking
    phantom_hack_progress: int     # 0 = not hacking, 1 = started, 2 = done
    phantom_hack_target: tuple | None
    specter_hack_progress: int
    specter_hack_target: tuple | None

    # Scores
    phantom_score: int
    specter_score: int

    # Turn info
    turn: int                      # 1-40
    max_turns: int                 # 40

    # Fog of War
    visibility_window_active: bool  # True on turns 5,10,15...
    phantom_scan_active: bool       # True if Phantom used Scan this turn
    specter_scan_active: bool

    # Vent pairs
    vent_pairs: dict               # { (r1,c1): (r2,c2), (r2,c2): (r1,c1), ... }

    # Alarm states
    alarm_disabled_until: dict     # { (row,col): turn_number }

    # Light disable states
    light_disabled_until: dict     # { (row,col): turn_number }

    # Blocked tiles
    blocked_until: dict            # { (row,col): turn_number }

    # Fragment respawn tracking
    fragment_respawn_queue: list   # list of turn numbers when a fragment respawns

    # Vaults hacked (for Intercept eligibility)
    phantom_hacked_vaults: list[tuple]
    specter_hacked_vaults: list[tuple]

    # Alarms triggered count (for scoring)
    phantom_alarms_triggered: int
    specter_alarms_triggered: int

    # Game status
    game_over: bool
    winner: str | None             # "phantom", "specter", or "draw"
    lose_reason: str | None        # "detection", "score", etc.
```

---

## Board Setup (board.py)

### Tile Types

```python
class TileType(Enum):
    EMPTY = "empty"
    VAULT = "vault"
    ALARM = "alarm"
    VENT = "vent"
    LIGHT = "light"
    FRAGMENT = "fragment"
```

### Board Generation Rules

Place the following on the 8×8 grid at game start (use `random.sample` on valid positions):

| Tile | Count | Placement Rule |
|------|-------|----------------|
| Vault | 3 | Not on start positions, not adjacent to each other |
| Alarm | 5 | Not on start positions |
| Vent | 4 | Placed as 2 pairs; store pairing in `vent_pairs` |
| Light | 8 | Random empty tiles |
| Fragment | 6 | Random empty tiles |
| Empty | rest | Default |

Start positions are always:
- Phantom: `(0, 0)` (top-left)
- Specter: `(7, 7)` (bottom-right)

These two tiles are **always EMPTY** and cannot have anything placed on them.

---

## Actions (actions.py)

All actions take `(state: GameState, player: str)` and return an updated `GameState`. Use `copy.deepcopy` to avoid mutating state directly.

---

### Move
```
move(state, player, direction)
direction: "up" | "down" | "left" | "right"
```
- Move player 1 tile in direction
- If new tile is out of bounds → action is invalid, player stays
- If new tile is LIGHT → `+5 detection` for that player
- If new tile is ALARM and alarm is active → `+3 detection` (passing near) OR `+15 detection` if they step directly on it
- If new tile is BLOCKED (from Sabotage) → action invalid, player stays
- Update position

---

### Hack (2-turn)
```
start_hack(state, player)
continue_hack(state, player)
```
**Rules:**
- Player must be standing on a VAULT or ALARM tile
- Turn 1: set `hack_progress = 1`, set `hack_target = current_pos`
- Turn 2: if player is still on the same tile, `hack_progress = 2` → complete hack
- If player moves away between turns: `hack_progress = 0`, `hack_target = None` (cancelled, no penalty)
- If collision occurs on the vault tile: both hacks reset

**On completion (Vault):**
- `player_score += 50`
- `player_detection += 10`
- Add vault to `player_hacked_vaults`

**On completion (Alarm):**
- `alarm_disabled_until[pos] = current_turn + 5`

---

### Fast Hack
```
fast_hack(state, player)
Cost: 6 RP
```
- Player must be on a VAULT tile
- Completes in **1 turn**
- Same results as normal vault hack: `+50 score`, `+10 detection`
- Deduct 6 RP before executing — if not enough RP, action is invalid

---

### Vent
```
use_vent(state, player)
Cost: 5 RP
```
- Player must be standing on a VENT tile
- Teleport to paired vent: use `state.vent_pairs[current_pos]`
- `+2 detection`
- If both players use vents simultaneously and share a pair: both teleport, `+5 detection` each

---

### Hide
```
hide(state, player)
Cost: 3 RP
```
- Player does not move
- `player_detection -= 10`
- Detection cannot go below 0

---

### Sabotage
```
sabotage_light(state, player, target_pos)
sabotage_block(state, player, target_pos)
Cost: 4 RP each
```
**Sabotage Light:**
- Target tile must be a LIGHT tile within 2 tiles (Manhattan distance) of the player
- `light_disabled_until[target_pos] = current_turn + 3`

**Sabotage Block:**
- Target tile must be EMPTY and within 2 tiles of the player
- `blocked_until[target_pos] = current_turn + 2`

---

### Scan
```
scan(state, player)
Cost: 4 RP
```
- Sets `player_scan_active = True`
- This flag is read by the fog of war system
- Lasts **1 turn only** — reset at end of turn

---

### Intercept
```
intercept(state, player)
Cost: 5 RP
```
- Player must be on a VAULT tile
- That vault must be in the **opponent's** `hacked_vaults` list
- Steal 25 score from opponent: `player_score += 25`, `opponent_score -= 25` (opponent score cannot go below 0)
- `player_detection += 15`

---

## Detection System (detection.py)

### Rules

```python
def apply_detection_event(state, player, event_type) -> GameState:
```

| Event | Change |
|-------|--------|
| `"light_step"` | +5 |
| `"near_alarm"` | +3 |
| `"trigger_alarm"` | +15 |
| `"hack_vault"` | +10 |
| `"vent_use"` | +2 |
| `"vent_collision"` | +5 |
| `"tile_collision"` | +5 |
| `"hide"` | -10 |
| `"intercept"` | +15 |

- Detection is clamped: `max(0, min(100, value))`
- If detection hits **100** → set `state.game_over = True`, `state.winner = opponent`, `state.lose_reason = "detection"`

### Near Alarm Check
Each time a player moves, check all 4 adjacent tiles. If any adjacent tile is an **active alarm** (not disabled), apply `+3 detection`.

---

## Fog of War (fog.py)

### Visibility Logic

```python
def can_see_opponent(state, viewer: str) -> bool:
```

Returns `True` if the viewer can see the opponent's position. Person B uses this to decide whether to render the opponent.

**Returns True when ANY of these are true:**
1. `state.visibility_window_active == True` (automatic reveal turns: 5, 10, 15, 20...)
2. Viewer is Phantom and `state.phantom_scan_active == True`
3. Viewer is Specter and `state.specter_scan_active == True`

**Otherwise returns False.**

### Visibility Window Activation

In the turn controller, at the **start of each turn**:
```python
state.visibility_window_active = (state.turn % 5 == 0)
```

At the **end of the turn**, reset:
```python
state.visibility_window_active = False
```

---

## Scoring Formula (engine.py)

```python
def calculate_score(state, player: str) -> int:
    if player == "phantom":
        vaults = len(state.phantom_hacked_vaults)
        detection = state.phantom_detection
        alarms = state.phantom_alarms_triggered
    else:
        vaults = len(state.specter_hacked_vaults)
        detection = state.specter_detection
        alarms = state.specter_alarms_triggered

    return (vaults * 50) - detection - (alarms * 20)
```

---

## Win / Loss Conditions (engine.py)

Check after every turn:

```python
def check_win_loss(state: GameState) -> GameState:
```

1. If `phantom_detection >= 100`:
   - `winner = "specter"`, `lose_reason = "phantom detected"`
2. If `specter_detection >= 100`:
   - `winner = "phantom"`, `lose_reason = "specter detected"`
3. If `turn >= 40`:
   - Compare `calculate_score(state, "phantom")` vs `calculate_score(state, "specter")`
   - Higher score wins; tie → `winner = "draw"`
4. Set `game_over = True` in all cases above

---

## Data Fragment Respawn (engine.py)

- When a fragment is collected, add an entry: `fragment_respawn_queue.append(turn + 5)`
- At the start of each turn, check if any entry in the queue equals `current_turn`
- If yes: place a new FRAGMENT tile on a **random EMPTY tile** (not occupied by either player)
- Remove that entry from the queue

---

## Specter AI (ai.py)

Specter plays **aggressively**. Implement a simple priority-based decision tree:

```python
def specter_decide(state: GameState) -> tuple[str, dict]:
    """Returns (action_name, action_kwargs)"""
```

### Decision Priority (check in order):

1. **If on a VAULT tile and not currently hacking** → `start_hack`
2. **If hack in progress and still on vault** → `continue_hack`
3. **If detection >= 70** → `hide` (if RP >= 3), else `move` away from alarms/lights
4. **If a vault is within 3 tiles** → move toward nearest vault
5. **If RP >= 6 and on vault** → `fast_hack`
6. **Else** → move toward nearest vault using simple pathfinding (BFS avoiding alarms/lights)

### BFS Pathfinding Helper
```python
def bfs_next_step(state, start, target, avoid_tile_types=[]) -> tuple[int,int]:
    """Returns the next position to move toward target, avoiding given tile types."""
```

---

## Turn Controller (engine.py)

```python
def run_turn(state: GameState, phantom_action: tuple) -> GameState:
    """
    phantom_action = (action_name, kwargs)
    e.g. ("move", {"direction": "right"})
         ("hack", {})
         ("scan", {})

    Returns updated GameState after the full turn resolves.
    """
```

### Turn Sequence (strict order):

1. Check visibility window: `state.visibility_window_active = (state.turn % 5 == 0)`
2. Get Specter's action from `specter_decide(state)`
3. Validate both actions (check RP, position requirements)
4. Deduct RP for special actions
5. Execute both actions **simultaneously**
6. Resolve collisions:
   - Same tile → both return to previous positions, `+5 detection` each
   - Same vault hack → both hack_progress reset
   - Same vent → both teleport, `+5 detection` each
7. Apply tile effects (light detection, alarm detection)
8. Update detection via `apply_detection_event()`
9. Check and collect Data Fragments
10. Process fragment respawn queue
11. Disable expired alarms, lights, blocked tiles
12. Reset scan flags
13. Reset visibility window: `state.visibility_window_active = False`
14. Increment turn: `state.turn += 1`
15. Check win/loss via `check_win_loss(state)`
16. Return updated state

---

## What You Expose to Person B

Person B needs only these from you:

```python
# state.py
GameState                    # the full state dataclass

# engine.py
def init_game() -> GameState
def run_turn(state, phantom_action) -> GameState
def calculate_score(state, player) -> int

# fog.py
def can_see_opponent(state, viewer) -> bool

# actions.py
VALID_ACTIONS = [
    "move", "hack", "fast_hack", "vent",
    "hide", "sabotage_light", "sabotage_block",
    "scan", "intercept"
]
```

Person B will call `init_game()` once, then call `run_turn()` each turn with the player's chosen action, and re-render using the returned state.

---

## Test Runner (main.py)

Build a simple print-based test loop so you can verify your logic without pygame:

```python
from game.engine import init_game, run_turn, calculate_score

state = init_game()

while not state.game_over:
    print(f"\n--- Turn {state.turn} ---")
    print(f"Phantom pos: {state.phantom_pos} | RP: {state.phantom_rp} | Det: {state.phantom_detection}")
    print(f"Specter pos: {state.specter_pos} | RP: {state.specter_rp} | Det: {state.specter_detection}")

    # Hardcode a test action for Phantom
    phantom_action = ("move", {"direction": "right"})

    state = run_turn(state, phantom_action)

print(f"\nGame Over! Winner: {state.winner}")
print(f"Phantom score: {calculate_score(state, 'phantom')}")
print(f"Specter score: {calculate_score(state, 'specter')}")
```

---

## Deliverable Checklist

Before handing off to Person B, verify:

- [ ] `init_game()` returns a valid GameState with full board
- [ ] All 9 actions work and mutate state correctly
- [ ] Detection clamps at 0 and 100
- [ ] Win/loss triggers correctly on detection = 100
- [ ] Win/loss triggers correctly at turn 40
- [ ] Hack cancels if player moves away mid-hack
- [ ] Alarms re-enable after 5 turns
- [ ] Fragments respawn at turn + 5 on a random tile
- [ ] `can_see_opponent()` returns correct values
- [ ] Specter AI makes valid moves every turn (never crashes)
- [ ] `run_turn()` returns a new state without mutating the input
- [ ] Test runner runs 40 turns without errors
