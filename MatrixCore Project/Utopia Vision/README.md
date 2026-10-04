# Utopia Lens Tour — Pass 59

Pass 59 is an AR coverage-continuity and visual cleanup pass built on Pass 58.

## Pass 59 changes
- Removed the existing city and exterior tree geometry entirely, including trunk collision and tree shadow sources.
- Retained the low physical park footprints, but hid those plain green slabs from the AR camera and added district-textured AR counterparts at the exact same footprints.
- Replaced all 24 broad flat `promenade_node` pads with district-textured AR pavement. These pads were the large muted rectangles that could dominate close AR views and make the world look blank or unfinished.
- Preserved shrubs and shoreline breakup outside Utopia as soft natural detail; only the rejected tree system was removed.
- Added `--ar-coverage-smoke` to lock the new park coverage, textured node pads, tree removal, and broad AR coverage categories.

## Preserved from Pass 58
- Public annex exterior AR coverage remains intact.
- Transit avenue and gate traversal repairs remain intact.
- Horizontal surface winding remains correct.
- Human residents retain gray physical bodies, synchronized AR counterparts, idle variation, and deterministic skeleton-following neon designs.
- Gleebs, interiors, Utopia systems, weather, audio, viewport protection and AR optimization remain unchanged.

## Runtime
- Panda3D 1.10.16
- 1920×1080 / 16:9 target
- `RUN_GAME.bat` on Windows or `python main.py`

## Controls
WASD move, Shift sprint, Space jump, mouse look, right mouse hold AR lens, L latch AR lens, V visor mode, ESC pause, F11 fullscreen. Arrow keys adjust AR time while paused.
