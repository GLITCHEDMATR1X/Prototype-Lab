# Entropy Asset Status — Pass 3

All shipped images and ordinary audio files pass decode checks.

## Active visual libraries

- galaxy tiles
- cockpit and ship-interior overlays
- player directional frames
- landed ship art
- procedural terrain and dungeon textures
- `assets/world_objects/decor/`
- `assets/world_objects/collision/`
- selected abstract forms from `assets/world_objects/hostile/` as environmental relics
- `assets/holograms/former_civ/` as ancient surface structures

Pass 2 reconnects the world-object and former-civilization libraries to active planetary generation. Missing former-civilization numbers 4, 39 and 48 remain unreferenced and do not cause runtime errors.

## Audio

Ship SFX remain active. Pass 3 adds 16 generated stereo WAV loops under `assets/sfx/ambience/`:

- 12 world-class surface loops
- 3 ruin loops
- 1 ship-interior hum

All 24 shipped audio files decode successfully. `assets/music/` still contains no playable music track; its README documents accepted formats. Ambient loops intentionally use reserved Sound channels rather than the music stream, leaving future soundtrack playback independent.
