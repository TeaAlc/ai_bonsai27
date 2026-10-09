# 🖼️ assets/ — Drop in your own sprites (optional)

The game works 100 % without any assets (procedural Canvas sprites). This folder is a **drop‑in point** for your own PNG art. If you don't put anything here, nothing changes.

> Full list of recommended free asset sites & licences: see **../ASSET_SOURCES.md**.

## Put files here

Create this sub‑folder if it doesn't exist:

```
assets/sprites/
```

and drop PNG files with **transparent backgrounds**, named exactly like this:

| File | Replaces |
|------|----------|
| `player.png` | The procedural blue dwarf (Bert) |
| `player_run.png` | Same (used instead of `player.png` if both exist) |
| `zombie.png` | Zombies |
| `soldier.png` | Enemy soldier |
| `boss.png` | Both boss captains |
| `bullet.png` | Bullets / pellets |
| `grenade.png` | Grenades |
| `ammo.png` | Ammo pickup |
| `gren.png` | Grenade pickup |
| `health.png` | Health‑pack pickup |
| `coin.png` | Gold coin pickup |
| `ammoBox.png` | Ammo‑box pickup |

Missing files are ignored and fall back to the procedural version — no errors, no load screen.

## Format checklist

- **PNG with alpha** (transparent background).
- **Square**, at least **64×64 px** (larger = crisp when downscaled). The game scales each image to a fixed size, so a square source keeps proportions clean.
- **Right‑facing** works best. The player and enemies rotate to face their target, so a single sprite is reoriented for you.
- **One entity per file** — no sprite sheets.

## Recommended source sizes

| Entity | Rendered at |
|--------|-------------|
| Player | 42 px |
| Enemy / boss | 38 px |
| Grenade | 14 px |
| Bullet | 12 px |
| Pickup | 22 px |

## How it's wired

1. On load, `loadAssets()` creates one `<Image>` per name above and points it at `assets/sprites/<name>.png`.
2. Every draw function calls `drawAssetAlt(g, [...names], x, y, size, flash)` and, if a valid image is present, draws it (with an optional white hit‑flash) instead of the procedural art.
3. A 404 or a corrupt image simply leaves the fallback in place.

## Verify

Reload `index.html`. If the player (and enemies/pickups, if you added them) now look like your PNGs, the pipeline is working. If they look the same as before, the images weren't found or failed to decode — check the file names and that the PNGs are valid (e.g. `python3 -c "from PIL import Image; Image.open('assets/sprites/player.png')"`).

## Remove them

Delete the files (or the whole `assets/` folder) at any time to go back to the procedural look.
