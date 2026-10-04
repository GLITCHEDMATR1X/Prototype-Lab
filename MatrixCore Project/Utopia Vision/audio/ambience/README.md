# Dynamic ambience assets

Pass 31 loads physical-world ambience zones from `ambience_zones.json` at startup.

## Replacing the ocean loop
The default ocean asset is:

`audio/ambience/ocean_loop.wav`

To replace it without changing code:

1. Stop the game.
2. Replace `ocean_loop.wav` with your own loop using the same filename.
3. Relaunch the game.

A stereo PCM WAV is the safest replacement format. OGG/MP3 may also work with Panda3D if the runtime codec supports them; when using another filename, update the `asset` field in `ambience_zones.json`.

## Volume / distance tuning
The current ocean zone uses `shape: radial_outer` because water surrounds Utopia on every side.

- `fade_start_radius`: distance from city center where the loop begins to become audible.
- `full_volume_radius`: distance where the loop reaches `max_volume`.
- `max_volume`: loudest allowed volume for this zone (0.0–1.0).
- `smoothing_seconds`: response time used to avoid abrupt volume changes.
- `master_volume`: global multiplier for all dynamic ambience zones.

The loop always has one owner. It begins at volume 0 and remains playing while its volume is smoothly adjusted. It is not repeatedly started/stopped when crossing a zone boundary.

## Future localized zones
The runtime also supports `shape: point` for localized ambience such as machinery, plaza hum, ventilation, generators, or interior equipment.

A point zone uses:

- `center: [x, y]`
- `full_radius`: full-volume radius around the source area
- `fade_radius`: distance where volume reaches 0
- `max_volume`
- `smoothing_seconds`

Dynamic ambience is physical-world audio. It is independent of the AR visor and AR-time override.
