# 🛠️ DwarF BUSTER — Spielkonzept

**Typ:** 2D Top-Down / Side-View Shooter (Survival-Shooter)
**Plattform:** Browser (HTML5 + Canvas + JavaScript, CSS für UI)
**Sprache:** Deutsch
**Art-Style:** Post-apkalypse, Pixel/Handgedrawn-Style, düster-moody Palette
**Playstyle:** Survival-Shooter mit Deckung, Vorrats-Management und Waffenvielfalt

---

## 1. Logline

Du bist **Bert**, ein letzter freier Zwerg in einem zerfallenden Dorf.
Münzgraben, Ruinen und verwachsende Zombies — du musst überleben, Munition
und Granaten jagen und dein Rüstungsdepot verteidigen, bis der Rettungshelikopter
kommt.

---

## 2. Spielziel

- **Überleben** mindestens **5 Minuten** (oder 3 Wellen).
- **Ziel-Score:** Töte möglichst viele Gegner, sammle so viel Munition wie möglich.
- **Ende:** Leben = 0 → Game Over. Überlebenszeit wird gemeldet.
- **Bonus:** Collectibles (Zaubertrünke, Goldmünzen) für Multipliers.

---

## 3. Spielwelt

Eine **post-apokalyptische Dorfkarte** (ca. 2000 × 1200 px, Kamera folgt dem Spieler):

| Element | Beschreibung |
|---|---|
| Ruinierte Häuser | 6–10 zerstörte cottages mit eingestürzten Dächern, zerbrochene Fenster |
| Bäume | Eiche/Birke mit abgeknickten Ästen, tote Strümpfe |
| Vorgärten | Zerdrückte Beete, umgekippte Zauntor, zerbrechliche Pfanne |
| Straßen | 2–3 asphaltierte Straßen mit Rissen, Ölfließen, Müll |
| Deckung | Wärdige Gräben, umgestürzte Bäume, Autoschrott |

---

## 4. Charaktere

### 🟢 Spieler — **Bert**
- 2D-Sprite mit **Animationen** (Idle, Lauf, Kneipen, Schießen, Treffer, Granatenwurf, Tod)
- **Stats:**
  - ❤️ **Leben:** 100 (Regeneration: 1/2s bei 50+ %)
  - 🧠 **Waffen-Auswahl:** Pistole / Gewehr / Shotgun
  - 🎒 **Inventar:** Max. 40 Schuss (Munition), 4 Granaten
- **Fähigkeiten:**
  - **Space:** Granatenwurf (Radar-Radius 150px, 8s Zündzeit)
  - **Q:** Sprint (Bewegung + 30 % für 3s, dann 1.5s Auspaus)

### 🔴 Feinde
| Feind | HP | Geschwindigkeit | Verhalten | Belohnung |
|---|---|---|---|---|
| 🧟 **Zombie** (Barn) | 80 | langsam (1.2 px/ms) | Lurk & Jagen (1.5x bei 100px) | 5 Munition (25 % Chance) |
| 🏴 **Zwerg-Soldat** (Feind) | 150 | schnell (2.5 px/ms) | Flankieren, Schießen (Distanz 300px) | 20 Schuss (30 % Chance) + Granate (10 %) |
| 💀 **Zombie-Kapitän** (Boss, alle 2 Min.) | 600 | schnell | Lasso, schwere Schläge, Spawn 2 Min. | 50 Munition + 4 Granaten + Heil |
| 🏳️ **Zwerg-Kapitän** (Boss, alle 2 Min.) | 700 | schnell | Lasso, schwere Schläge, Spawn 2 Min. | 60 Munition + 5 Granaten + Heil |

### 🔥 Projektile
| Waffe | Dmg | Feuerrate | Reichweite |
|---|---|---|---|
| **Pistole** | 25 | 400ms | 400px |
| **Gewehr** | 35 | 250ms | 600px |
| **Shotgun** | 15 × 5 Pellet | 1200ms | 250px |
| **Granate** | 100 (Radius 100px) | 3sCooldown | 300px Wurf |

### 📦 Collectibles (verschwinden nach 8s, pulsierender Glow)
| Item | Effekt |
|---|---|
| 🧯 **Munition** (5–10) | Füllt Munition |
| 💣 **Granate** | +1 Granate |
| ❤️ **Heilpak** | +30 Leben (max. 100) |
| ⭐ **Goldmünze** | +25 % Score Multiplikator (max. 5x, 30s) |
| 🔋 **Ammo-Box** | +10 Schuss, +10 s Regeneration |

---

## 5. Gameplay-Schleife (eine Runde)

1. **Spawn:** Bert am Zentralkreuz der Dorfstraßen.
2. **Wave 1 (t=0s):** 5 Zombies (aus der Nähe).
3. **Wave 2 (t=45s):** 8 Zombies + 3 Zwerg-Soldaten.
4. **Wave 3 (t=90s):** 10 Zombies + 5 Soldaten + **1 Boss** (alternierend).
5. **Wave 4 (t=140s):** 12 Zombies + 6 Soldaten + **1 Boss**.
6. **Wave 5 (t=190s):** 15 Zombies + 8 Soldaten + **1 Boss**.
7. **Overload:** t=250s, 20 enemies, 2x Speed.
8. **Victory:** Wenn t ≥ 250s überlebt → **Rettungshelikopter** (Win-Screen).

**Wave-Spawns** kommen immer aus den **Kartenecken** (Spawn-Points: N, S, E, W) mit 5s Vorwarnung (Blinken + Sound).

### Tötungs-Mechanik
- Gegner haben ein **Feind-Frame** (200ms) bei Kollision → Schaden.
- **Schadens-Feedback:** Blut (Partikel), Screen Shake, Fluff (0.5s).
- **Gegner-Absterben:** Explosion/Blut-Partikel, Drop-Vorschuss (5s).

---

## 6. Steuerung

| Taste | Aktion |
|---|---|
| **WASD / Pfeil** | Bewegung (8-directional) |
| **Maus** | Zielrichtung |
| **LMB** | Schießen (auto-firing) |
| **RMB / Space** | Granatenwurf |
| **Q** | Sprint |
| **1 / 2 / 3** | Waffe wechseln (Pistole/Gewehr/Shotgun) |
| **P** | Pause |
| **R** | Reset (Game Over) |

---

## 7. UI / HUD

```
┌──────────────────────────────────────────────────────┐
│ ❤️ 100/100   💣 4/4   🧯 32/40   ⭐ x2.5x          │
│ 🎯 Pistole (3/10)  [1] [2] [3]                     │
│ [W] 1s   [S] 0s   [R] 3s                           │
│ Score: 1520  Wave: 2/5  Time: 1:23                  │
│ [P] Pause  [R] Reset                               │
└──────────────────────────────────────────────────────┘
```

- **Damage Flash:** Screen wird rot (0.2s) bei 30+ % Lebensverlust.
- **Healing-Glow:** Grün (0.5s) bei Heilung.
- **Kill-Combo:** "×3 COMBO!" wenn 3+ Kills in 5s.

---

## 8. Sound (optional, wenn Assets verfügbar)

| Event | Sound |
|---|---|
| Schuss (Pistole) | `pop` |
| Schuss (Shotgun) | `boom` |
| Granatenwurf | `fwoosh` |
| Explosion | `boom` + `thump` |
| Treffer (Gegner) | `hit` |
| Treffer (Spieler) | `ouch` |
| Item-Pickup | `coin` |
| Wave-Sound | `horn` |
| Boss-Sound | `roar` |
| Music | Lo-fi Dark Loop (60 BPM) |

> **Falls keine Sound-Assets verfügbar:** Fallback auf WebAudio-API-Synthese.

---

## 9. Technische Architektur

### Dateistruktur
```
game/
├── index.html           # Einstieg, CSS + JS + Assets
├── styles.css           # UI, HUD, Screens
├── game.js              # Haupt-Game-Loop
│   ├── constants.js     # Konstanten, Colors, Sounds
│   ├── classes/         # Entities (Player, Enemy, Projectile, Pickup)
│   ├── systems/         # Systems (Physics, Input, Camera)
│   └── assets/          # Sprites, Sound, Backgrounds
└── GAME_CONCEPT.md
```

### Tech-Stack
- **Canvas 2D API** (50 fps Target, Delta-Time)
- **Modular:** ES6-Module (`<script type="module">`)
- **State-Machine:** `menu → playing → paused → game_over → victory`
- **Asset-Loader:** Promise-basierter Preloader (Lade-Screen)
- **No External Dependencies** (optional: PixiJS falls Performance nötig)

### Performance-Ziele
- < 100 Entitäten (Player + 15 enemies + 30 projectiles + 20 pickups)
- < 200 Partikel gleichzeitig
- < 50 FPS auf mittlere Hardware

---

## 10. Art-Direction

### Farbpalette (Post-Apocalypse)
```
#1a1a1a  #2c2c2c  #5c5c5c  #8c8c8c  #b5b5b5
#7c5a2e  #5e4a20  #3a2a1a  #2a1a0a  #0a0a0a
#66cc66  #ffaa00  #ff3333  #00ccff  #ffffff
```

- **Background:** Dark brown/grey, mit Noise-Texturen (procedural)
- **Sprites:** Pixel-Style mit 2px Anti-Aliasing, 48×48 px Base-Grid
- **Particles:**
  - Blood: `#800000` (circular)
  - Explosion: `#ffaa00` + `#ff3333` (radial)
  - Muzzle Flash: `#ffffff` (triangle)
  - Smoke: `#888888` (circular, fade)

### Animations (procedural, ohne Sprite-Sheets)
- **Player:**
  - Idle: Kopf wackelt (sin(t/500))
  - Lauf: Beine alternierend (step = 1)
  - Schießen: Arm-Knick (0.2s)
  - Granatenwurf: Arm-Knick + Body-Tilt (0.3s)
  - Treffer: Flash + Tilt (0.15s)
- **Enemies:**
  - Zombie: Wackeln (sin(t/400))
  - Soldier: Walk-Animation (step)
  - Boss: Puls (scale = 1 + sin(t/300) * 0.05)

---

## 11. Milestones

- **Phase 1:** ✅ Konzept (dieses Dokument)
- **Phase 2:** Umsetzung (Assets + Code)
  - 2a: Asset-Recherche (craftpix.net, itch.io, gameart2d.com)
  - 2b: Grund-Loop (Player Movement + Shooting + Enemies)
  - 2c: Wave-System + HUD
  - 2d: Particles + Feedback
  - 2e: Sound (WebAudio-Synth)
  - 2f: Polish (Combo-System, Screen Shake, Music)

---

## 12. Open Questions

- [ ] **Sound:** Echte Assets (MP3/OGG) oder WebAudio-Synthese? → *Synthese (keine Assets nötig)*
- [ ] **Sprites:** Echte Assets oder procedural (Canvas-Rendering)? → *Procedural* (keine Asset-Abhängigkeiten)
- [ ] **Mobile:** Touch-Support? → *Nein (Desktop-Only)*
- [ ] **Multiplayer:** Keine
- [ ] **Level-Design:** Eine große Karte (2000×1200) vs. mehrere Level? → *Eine große Karte*

---

## 13. Referenzen

- **Celeste** (Difficulty Balance)
- **Dead Cells** (Combo-System)
- **Downwell** (Top-Down Shooter)
- **Enter the Gungeon** (Roguelike Mechanics)
- **Dwarf Fortress** (Post-Apocalyptic Art Direction)
