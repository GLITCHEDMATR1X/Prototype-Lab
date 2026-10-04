# Open Void (reserved stratum)

The top band in `../strata.json` is open-ended. It ships with sparse jellyfish and no floating assets, and it is the slot for the next upward biome.

To add one:
1. Drop `*.py` files here, or give a new band its own folder name in `strata.json` with a higher `floor`.
2. Each file declares `STRATA_OBJECT = {"id": ..., "weight": 1.0, "per_cell": 0.5}` and `build(parent, x, y, z, rng, metadata)`, which returns a NodePath. It can also define `update(node, time_value)`.
3. Files that start with `_` are skipped. A file that fails to import is skipped with a log line, and the game keeps running.

The `holocore_line_kit` helpers (`new_lines`, `polyline`, `ring`, `wire_sphere`, `finish`) keep new assets in the same neon line style as the seabed flora.
