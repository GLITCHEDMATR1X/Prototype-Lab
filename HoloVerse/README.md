# HoloVerse // MatrixCore Observatory

Run `main.py` with Python 3.11+ and the packages in `requirements.txt`
(Panda3D 1.10, pygame, numpy, Pillow, opencv-python).

## Where your saves go

HoloVerse never writes into its own game folder. Settings, progression, region saves,
the Dimension Archive, caches and logs are kept per player in:

- Windows: `%LOCALAPPDATA%\GLITCHED MATRIX\HoloVerse\`
- macOS: `~/Library/Application Support/GLITCHED MATRIX/HoloVerse/`
- Linux: `~/.local/share/glitched-matrix/holoverse/`

Inside: `dimension_archive.json` (which planets/dimensions you have unlocked),
`holospace_cockpit_choice.json`, `saves\` (settings and progress), `cache\` (prepared
HoloSpace planet textures - safe to delete) and `logs\`.
Delete that folder to start completely fresh. Other Glitched Matrix games keep their
own folders beside it (for example `GLITCHED MATRIX\INDIGO GIANT`).

## If the game closes or crashes

Send these from the `logs` folder above:

- `crash.log` - a Python error that stopped the game
- `native_crash.log` - a crash inside Panda3D, the graphics driver or audio
- `latest.log` - everything the game printed during the last session

## The world

- **MatrixCore hub** with eight region artifacts around it (Forests, Green Hills, Mushroom,
  Desert, Ice, Urban, Metropolis, HoloSpace). Walk up to one and press E to travel.
- **Region guides** (IO, Vanta, Solace, Nyx, Ember, the Archivist, Sable, Mirror, Orbit)
  each open a dimension gate from their dialogue.
- **Gleebs** keeps the Dimension Archive. Archive entries unlock when you first fly into
  that dimension's planet in HoloSpace.
- **HoloSpace**: the warp from the HoloSpace artifact (or the ascent) leads to ship flight
  among the dimension planets and Dyson Prime. Guard wings defend the planets.

## Controls

| Where | Keys |
|---|---|
| Everywhere | E use / enter, TAB return to MatrixCore, ESC pause, H help, F3 hide/show HUD |
| HoloSpace | mouse steer, W/S throttle, 1-5 throttle presets, SHIFT boost, LMB lasers / enter a planet, T cycle nav target, C cockpit colour theme, J supercruise |
| Dimensions | their own controls; ESC always opens the HoloVerse pause card (RESUME / DIMENSION MENU when the dimension has its own menu / RETURN TO MATRIXCORE); TAB returns home. Own-window dimensions (Vector Wars, Operation StarFall, Afterlife of IO) return when you quit them from their own menu |

## Music

All tracks live in `assets/audio/regions/` and are mapped in `assets/audio/region_music.json`.
`holoverse.mp3` is the HoloVerse song (title screen, hub and the flat region); the other
files are one track per region plus `holocore.mp3` for HoloCore. Replace any file with your
own MP3 of the same name. A missing file means that area is silent. Dimensions other than
HoloCore play their own soundtracks.

## Editable settings

- `assets/config/holospace_cockpit.json` - HoloSpace cockpit colours and window shape
  (delete it to restore the defaults).
- `assets/audio/region_music.json` - music files and per-track volume.
