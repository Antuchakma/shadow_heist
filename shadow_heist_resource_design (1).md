# Shadow Heist – Complete Game Design (Resource + Fog of War Edition)

---

## 🎮 Game Overview

Shadow Heist is a turn-based stealth strategy game played on an **8×8 grid**.

**Game Mode: Player vs AI**
- You control **Phantom** directly
- The computer controls **Specter** automatically

Two agents compete:
- **Phantom** (Player) → Slow, careful, stealthy
- **Specter** (AI) → Fast, aggressive, risky

Your goal:
👉 **Collect more score than your opponent without getting detected**

---

## 🧩 Game Board (8×8 Grid)

Each tile on the board can be:

- 🟦 Empty → Move freely
- 🟨 Vault → Main objective (gives score)
- 🟥 Alarm → Increases detection
- 🟩 Vent → Teleport between vents
- 🟪 Light → Increases detection
- 🟧 Data Fragment → Gives Resource Points (RP)

---

## 🕹️ Game Setup

- Grid Size: **8×8**
- Vaults: **3**
- Alarms: **5**
- Vents: **4 (2 fixed pairs, randomized each game)**
- Light Tiles: **8**
- Data Fragments: **6**
- Turn Limit: **40 turns**

Start Positions:
- Phantom → Top-left corner
- Specter → Bottom-right corner

### Vent Pairing
Vents are grouped into **2 fixed pairs** at the start of each game:
- Pair A: Vent A1 ↔ Vent A2 (entering either teleports you to the other)
- Pair B: Vent B1 ↔ Vent B2
- Pairs are randomized each game but shown on the map at start

---

# 💎 Resource System (RP)

Each player has **Resource Points (RP)**.

- Start: **5 RP**
- Max: **20 RP**

---

## 🪙 How to Gain RP

### 1. Data Fragments
- Each gives: **+2 RP**
- Disappears after collection
- Respawns every **5 turns at a random empty tile**

> **Note:** Passive gain has been removed. RP must be earned by collecting Data Fragments — this forces both players to actively contest the board.

---

# ⚡ Actions

## 🟢 Free Actions

### Move
- Move 1 tile (up/down/left/right)
- If in light → **+5 detection**

---

### Hack
- Takes **2 consecutive turns** to complete
- The player must **stay on the vault tile for both turns** — moving away cancels the hack with no reward
- The hack can be **interrupted** if both players collide on the vault tile (both delayed 1 turn, hack resets)

**Vault Hack result:**
- +50 score
- +10 detection

**Alarm Hack result:**
- Alarm **disabled for 5 turns** (then reactivates)

---

## 🔵 Special Actions (Cost RP)

### Vent (Cost: 5 RP)
- Teleport to the paired vent tile
- +2 detection
- If both players use the same vent simultaneously: both arrive at the destination, +5 detection each

---

### Sabotage (Cost: 4 RP)
Choose one:
- Disable a light for 3 turns
- Block a tile for 2 turns (no one can enter)

---

### Hide (Cost: 3 RP)
- Stay still
- Reduce detection by **10**

---

### Scan (Cost: 4 RP) 👁️
- Reveal opponent's **exact position** instantly
- Duration: **1 turn**
- Triggers a visible **flash effect** on screen when activated

---

### Fast Hack (Cost: 6 RP) *(Optional)*
- Complete hack in **1 turn** instead of 2
- Still grants +10 detection

---

### Intercept (Cost: 5 RP) *(New)*
- Can only be used on a vault tile that the opponent has **already hacked** this game
- Steal **25 score** from the opponent (half of the vault's value)
- +15 detection for the intercepting player
- Rewards aggressive play and punishes opponents who hack carelessly

---

# 👁️ Fog of War System

## 🧠 Simple Idea

You **cannot always see your opponent**.

Most of the time:
👉 The opponent is **invisible**

---

## 🔍 Visibility Rules

### ❌ Default State (Hidden)
- Opponent position is **unknown**
- You must **guess and predict**

---

### 👀 Visibility Window (Automatic Reveal)

Every **5 turns**, a special event happens:

- Duration: **1 turn**
- Both players can see each other's **exact position**
- A **visual flash effect** plays in pygame to signal the reveal window

After that:
👉 Opponent becomes hidden again

---

## 👁️ Manual Reveal (Scan Ability)

Instead of waiting, you can use:

### Scan (Cost: 4 RP)
- Reveal opponent instantly
- Lasts **1 turn**

---

# 👁️ Detection System

Each player has detection: **0 → 100**

| Event | Detection |
|------|----------|
| Standing in light | +5 |
| Near alarm | +3 |
| Trigger alarm | +15 |
| Hack vault | +10 |
| Vent | +2 |
| Hide | -10 |
| Collision on same tile | +5 |
| Intercept | +15 |

👉 If detection reaches **100 → YOU LOSE immediately**

> **Clarification:** Detection in the final score formula uses your **detection value at game end**, not a cumulative total.

---

# 💥 Collision Rules

If both players:

- **Move to same tile** → both stay in their previous positions, +5 detection each
- **Try same vault** → hack for both players is cancelled and reset; neither gains score that turn
- **Use same vent** → both successfully teleport to the destination tile, +5 detection each

---

# 🏆 Scoring System

Final Score:

```
Score = (Vaults Hacked × 50) − Final Detection Value − (Alarms Triggered × 20)
```

- **Vaults Hacked**: number of vaults successfully completed (2-turn hack or Fast Hack)
- **Final Detection Value**: your detection meter at the end of turn 40 (or when opponent is caught)
- **Alarms Triggered**: number of times you walked onto an active alarm tile

---

# 🏁 Winning Conditions

You win if:

1. Opponent detection reaches **100**
2. Game ends (40 turns) and you have **higher score**

---

# ❌ Losing Conditions

You lose if:

- Detection reaches **100**
- Lower score at end

---

# 🔄 Turn Flow (Step-by-Step)

Each turn:

1. Player chooses an action; Specter AI chooses its action
2. Check if enough RP (for special moves)
3. Execute actions simultaneously
4. Resolve collisions if any
5. Update positions
6. Update detection
7. Award RP from Data Fragments if collected
8. Check for Data Fragment respawn (every 5 turns)
9. Check visibility window (every 5 turns → flash reveal)
10. Check win/loss conditions

---

# 🖥️ Pygame UI Layout

Plan your screen layout before coding:

```
+---------------------------+----------+
|                           | PHANTOM  |
|        8×8 GRID           | RP: 12   |
|                           | Det: 35  |
|                           +----------+
|                           | SPECTER  |
|                           | RP: 8    |
|                           | Det: 50  |
|                           +----------+
|                           | Turn: 14 |
|                           | FOW: OFF |
+---------------------------+----------+
```

- **Detection bars** shown visually for both players
- **Fog of War flash** — brief screen effect every 5 turns when reveal window opens
- **Vent pair labels** — show A1/A2/B1/B2 on the map

---

# 🧠 Example (Easy to Imagine)

Turn 5:
- Visibility window activates 👀 (flash effect plays)
- Phantom sees Specter near a vault

Turn 6:
- Specter disappears again

Turn 7:
- Phantom uses **Scan (−4 RP)**
👉 Sees Specter again

Turn 8:
- Specter hacks Vault 2
- Phantom moves onto Vault 2 and uses **Intercept (−5 RP)**
👉 Steals 25 score, +15 detection

---

# 🎯 Strategy Ideas

## Phantom (Stealth Player)
- Collect Data Fragments to build RP
- Use Scan carefully before committing to a vault
- Avoid light tiles and alarms
- Play long-term; use Intercept as a late-game threat

---

## Specter (Aggressive AI)
- Rushes vaults early
- Uses Fast Hack to take vaults before Phantom can react
- Takes risks with detection
- Forces Phantom to spend RP on Scan to track it

---

# 🌟 Why This Game is Fun

- You can't always see your opponent 👁️
- RP must be earned — no free passive income 💎
- Every move is a decision 🤔
- Risk vs reward gameplay ⚖️
- Intercept mechanic creates dynamic comebacks 🔥
- Different play styles reward different strategies

---

# 🚀 Final Result

This version of Shadow Heist combines:

- Stealth
- Strategy
- Resource management
- Hidden information
- Dynamic board control (fragment contesting, intercepts)

👉 Making it a **deep, smart, and exciting AI game**
