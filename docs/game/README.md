# 🛠️ DWARF BUSTER

A post‑apocalyptic 2D top‑down survival shooter. You are **Bert**, the last free dwarf in a ruined village. Fight off waves of zombies and enemy dwarves, scavenge ammo and grenades, and survive **5 waves (250 seconds)** until the rescue helicopter arrives.

Built with **vanilla HTML5 + Canvas 2D + JavaScript**. No libraries, no build step. Every sprite is drawn procedurally on a `<canvas>` each frame, and every sound is synthesized at runtime with the **WebAudio API** — the game is completely self‑contained and works by simply double‑clicking `index.html`.

## ▶ How to run

| Method | Command | Notes |
|--------|---------|-------|
| **Double‑click** | Open `index.html` in a browser | Works via `file://` (no server needed) |
| Local server | `python3 -m http.server 8888` → open `http://localhost:8888/` | Good if you edit a lot |
| Headless test server | `python3 server.py 8891` → `http://127.0.0.1:8891/` | Adds `/img?hold=N` + `/dbg` for automated screenshot tests |

> The whole game is a **single classic (non‑module) script** (`game.js`). This is deliberate: ES modules fail on `file://` due to CORS. A classic script with no imports works from a double‑click.

## 🎮 Controls

| Key | Action |
|-----|--------|
| **WASD / Arrow keys** | Move (8‑directional) |
| **Mouse** | Aim |
| **Left‑click** | Fire (auto if the weapon is set to auto) |
| **G / Right‑click / Space** | Throw grenade |
| **Q** | Sprint (≈35 % faster for 3 s, then 1.5 s recovery) |
| **1 / 2 / 3** | Weapon: Pistol / Rifle / Shotgun |
| **P** | Pause / Resume |
| **R** | Restart (Game Over / Victory) |

## 🌍 Gameplay

- **World:** one ruined village (~2000×1200 px) with crumbled houses, trees, front yards and two crossing roads. A camera follows Bert.
- **Waves** (spawn from the N/S/E/W edges of the map with a short blink + horn warning):

  | Wave | Time | Enemies |
  |------|------|---------|
  | 1 | 0 s | 5 zombies |
  | 2 | 45 s | 8 zombies + 3 soldiers |
  | 3 | 90 s | 10 zombies + 5 soldiers + 1 boss |
  | 4 | 140 s | 12 zombies + 6 soldiers + 1 boss |
  | 5 | 190 s | 15 zombies + 8 soldiers + 1 boss |
  | Overload | 250 s | 20 enemies, 1.4× speed — **survive → Victory** |

  The boss is an alternating **Zombie‑Captain** or **Dwarf‑Captain** (lunges, and the dwarf one throws grenades).

- **Weapons:**
  | Weapon | Dmg | Mags | Fire rate | Range | Auto |
  |--------|-----|------|-----------|-------|------|
  | Pistole | 25 | 10 | 0.4 s | 400 | no |
  | Gewehr | 35 | 30 | 0.25 s | 600 | yes |
  | Shotgun | 15×5 | 5 | 1.2 s | 260 | no |

- **Grenades:** 4 at start (up to 8), 1.5 s fuse, 100 px blast radius, 80 dmg, 1.2 s cooldown.
- **Enemy shots look like yours:** soldiers fire bullets with the same yellow tracer, but a **slower speed (666 px/s)** than your own (900 px/s) so you have more time to dodge. Each shot is telegraphed by a bright **muzzle flash** at the shooter’s gun (so you see where it fired from) plus a sharp high “pew” — you track the yellow bullet and sidestep. All enemy attacks are projectiles (soldier bullets, dwarf‑captain grenades) except pure melee (zombie claws, boss lunges).
- **Enemy pathfinding (A\*):** enemies navigate the village with an A\* path on a 20‑px grid over the solid world objects (houses, trees, fences, cars, barrels, rubble). Each enemy follows walkable cell‑centres, re‑paths when the player strays or the path runs out, and falls back to a direct approach when no path exists. The static village is pre‑built once (100×60 grid) so per‑frame cost is just following the cached waypoint list.
- **Pickups** (drop from dead enemies or spawn in the world, 8 s TTL, 30 s for gold):
  - 🧯 **Ammo** — refill ammo (5–10)
  - 💣 **Grenade** — +1 grenade
  - ❤️ **Health pack** — +30 HP
  - ⭐ **Gold coin** — +25 % score multiplier (stacks up to 5×)
  - 📦 **Ammo box** — +10 ammo and extends regen
- **Bert:** 100 HP, regenerates 8 HP/s when HP > 40 and no hit for 3 s.
- **Score & combo:** each kill earns points; a combo multiplier ramps up for consecutive kills (5 s window).
- **Win / Lose:** HP ≤ 0 → **Game Over**; survive to 250 s → **Rettung** (rescue helicopter).

## 📁 Project structure

```
game/
├── index.html          # Single entry point (HUD, screens, <canvas>)
├── styles.css          # UI / HUD / screen styling
├── game.js             # The entire game (game loop, systems, art, sound) — ~2000 lines
├── GAME_CONCEPT.md     # Full game design document
├── README.md           # This file
├── assets/
│   └── README.md       # How to drop in your own PNG sprites (optional)
├── server.py           # Local dev server + /img?hold + /dbg (for headless testing)
├── node_test.js        # Node VM smoke‑test harness (runs game.js in Node, catches crashes)
├── node_assert_test.js # deterministic assertions (WASD + grenade fly/fuse/self‑damage)
└── node_path_test.js   # headless A* pathfinding / world‑connectivity checks
```

## 🛠 Tech notes

- **Canvas 2D** at a fixed 960×540 logical resolution, delta‑time driven, ~60 fps target.
- **State machine:** `MENU → PLAYING → PAUSED → GAMEOVER → VICTORY`.
- **Rendering:** 100 % procedural — the static village is pre‑rendered to an off‑screen canvas; entities (player, enemies, projectiles, pickups, particles) are drawn with Canvas primitives each frame, with walk‑bob, head‑wiggle, gun recoil and hit‑flash.
- **Sound:** fully synthesized with WebAudio (gunshots, explosions, pickups, wave horn, a dark lo‑fi music loop). No audio files.
- **Optional asset pipeline:** if you drop real PNG sprites into `assets/sprites/`, the game loads them and draws them **instead of** the procedural sprites (see `assets/README.md`). Missing assets simply fall back to procedural rendering — there is no load screen and nothing blocks.

## 🧪 Testing & verification

The game ships with a small set of test hooks that only activate through URL query parameters, so normal play is completely unaffected:

- `?t=1` — auto‑play bot (movement, aiming, shooting) for smoke‑testing
- `?t=2` — forced Game Over
- `?t=3` — forced Victory
- `?shot=1` — debug

Headless screenshot capture (Firefox):
```bash
python3 server.py 8891
firefox --headless --screenshot=/tmp/menu.png "http://127.0.0.1:8891/index.html?t=0&hold=3"
firefox --headless --screenshot=/tmp/play.png  "http://127.0.0.1:8891/index.html?t=16&hold=16"
firefox --headless --screenshot=/tmp/win.png   "http://127.0.0.1:8891/index.html?t=3&hold=5"
```
(`/img?hold=N` sleeps `N` seconds so the browser screenshot lands at the right moment.)

Syntax + crash checks:
```bash
node --check game.js            # parse check
node node_test.js               # runs 400 frames in a Node VM with a fake DOM/AudioContext
node node_assert_test.js        # deterministic assertions (WASD movement + grenade fly/fuse)
node node_path_test.js          # inspects the real A* grid: blocked cells, path lengths, world connectivity
```

The A\* test confirms the real village grid has a fully‑connected walkable space, that pathfind returns valid lengths for long routes (e.g. 200→1800 across the map), and that enemies spawn in walkable cells.
