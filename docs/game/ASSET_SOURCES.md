# 🎨 Asset Sources — DWARF BUSTER

This game ships with **no external asset files**. Every sprite is drawn procedurally and every sound is synthesized with WebAudio, so the project runs from a double‑click (`file://`) with zero dependencies. That said, an **optional asset pipeline** is built in: if you drop real PNG sprites into `assets/sprites/`, the game loads them and renders them in place of the procedural versions.

This document records where to find suitable free assets and how the pipeline was set up.

---

## 1. What was searched (Phase 2a)

The concept called for free 2D art from three well‑known repositories:

| Site | Purpose | Result |
|------|---------|--------|
| [craftpix.net](https://craftpix.net) | Free game art (2D pixel, tilemaps, characters) | Not machine‑fetchable — the site is a JavaScript‑driven storefront (SPA), so static HTTP requests return the app shell, not the asset data. Requires JS / a real browser or their API/subscription. |
| [itch.io](https://itch.io) | Free game‑asset packs (2D pixel, dark themes) | Same as CraftPix — content is rendered client‑side / behind auth for some packs; static fetches do not expose downloadable assets. |
| [gameart2d.com](https://gameart2d.com) | 2D game art, characters, backgrounds | Site is JS‑rendered and bot‑throttled; not reliably fetchable headlessly. |

**Conclusion:** none of the three could be scraped directly in a headless environment, so the build shipped **procedural‑first**. The optional loader was kept so that, once real art is chosen (in a browser, manually), it can be dropped in without code changes.

---

## 2. Recommended free sources (with licences)

Pick assets you like in a normal browser and drop them into `assets/sprites/` (see §4). Focused on *dark / post‑apocalyptic, 2D, top‑down or pixel, with transparency*.

### Character / creature sprites

| Source | Licence | What to grab |
|--------|---------|--------------|
| [OpenGameArt.org](https://opengameart.org) | Mix of **CC0 / CC‑BY** per item (check the asset page) | Zombies, dwarf/roguish characters, soldiers, top‑down characters, pixel creatures. Search: *zombie pixel*, *top‑down character*, *dwarf*, *soldier pixel*. |
| [CraftPix](https://craftpix.net) | Free (see their licence; some packs require attribution) | Pixel‑art character packs and top‑down hero/enemy sets. |
| [Kenney.nl](https://kenney.nl) | **CC0** | The "Pixel" packs are small and clean; less thematically dark but free and permissive. |
| [Ludicraft](https://ludicraft.com) | CC‑BY / custom | Top‑down pixel characters with multiple facing directions. |
| [itch.io — free packs](https://itch.io) | Per‑pack (many **CC0/CC‑BY**) | Search *2D pixel shooter*, *post apocalyptic*, *zombie top‑down*, *dark pixel characters*. |

### Sound (optional — the game synthesizes everything by default)

| Source | Licence | Notes |
|--------|---------|-------|
| [OpenGameArt.org](https://opengameart.org) | Per‑item | Gunshots, explosions, pickups, horns. |
| [freesound.org](https://freesound.org) | Mostly **CC‑BY / CC0** | Large library; filter by "game". |
| [Zapsplat](https://www.zapsplat.com) | Free with attribution | Huge, well‑organised SFX sets. |

> If you add real audio files, wire them into the sound section of `game.js` (`SFX.*`); the synth calls are easy to swap for `new Audio(url).play()` or an `AudioContext` + `decodeAudioData` path.

---

## 3. What the loader expects

The loader (`loadAssets()` in `game.js`) probes this exact set of filenames and silently falls back to procedural rendering for any that are missing:

| Expected file (in `assets/sprites/`) | Used for |
|--------------------------------------|----------|
| `player.png` | Player body |
| `player_run.png` | Player body (used instead of `player.png` if present) |
| `zombie.png` | Zombie |
| `soldier.png` | Soldier |
| `boss.png` | Either boss captain (zombie or dwarf) |
| `bullet.png` | Bullet / pellet / enemy bullet |
| `grenade.png` | Thrown grenade |
| `ammo.png` | Ammo pickup |
| `gren.png` | Grenade pickup |
| `health.png` | Health‑pack pickup |
| `coin.png` | Gold coin pickup |
| `ammoBox.png` | Ammo‑box pickup |

The loader never blocks the menu: images that 404 simply fall through to `onerror` and the procedural fallback is used. A safety `setTimeout` marks the set `ready` after ~800 ms regardless.

---

## 4. How to drop in real art

1. **Create the folder** if it doesn't exist: `assets/sprites/`.
2. **Export square PNGs with a transparent background.** Recommended minimum **64×64** (the game stretches them to a fixed draw size, so a larger source keeps them crisp).
3. **Name them exactly** as in the table above (case‑sensitive).
4. **Orientation:** sprites are drawn in the same transformed space as the procedural version — the player and enemies **rotate to face their target/aim direction**, so a single right‑facing sprite will be rotated around. For a cleaner result, a top‑down or front‑facing sprite works best; if your art has fixed facing, it will still display but may appear rotated.
5. **Re‑reload** `index.html` — the game picks up the sprites on load. Nothing else to change.

**Draw sizes used by the game (target for your source art):**

| Entity | Draw size |
|--------|-----------|
| Player | 42 px |
| Enemy / boss | 38 px |
| Grenade | 14 px |
| Bullet | 12 px |
| Pickup | 22 px |

---

## 5. Verification that the pipeline works

The loader → `drawAsset` / `drawAssetAlt` → draw‑function path was verified end‑to‑end by dropping two test sprites (`player.png`, `player_run.png`) into `assets/sprites/` and confirming the player renders as the image instead of the procedural dwarf, then removing them. The same `drawAssetAlt(g, [...names], x, y, size, flash)` helper is called from:

- `drawPlayer` → `['player_run','player']`
- `drawEnemy` → zombie / soldier / `boss`
- `drawProjectile` → grenade / bullet
- `drawPickup` → `ammo / gren / health / coin / ammoBox`

Each returns the moment a valid image is available; a `flash` argument tints the image white on hit, mirroring the procedural hit‑flash.
