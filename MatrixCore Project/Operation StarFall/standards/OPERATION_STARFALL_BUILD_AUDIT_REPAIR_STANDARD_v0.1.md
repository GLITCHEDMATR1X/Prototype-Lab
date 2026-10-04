# Operation StarFall Build Audit Repair Standard v0.1

A repaired StarFall build must not ship nested full-package zips, stale root pass files, Python bytecode/cache folders, root-level screenshots, or old screenshot proof sets mixed into the active release.

## Required repair rules

- The release root contains only the current pass report/validation/changelog files.
- Old pass reports live under `docs/pass_history/`.
- No `.zip` files are shipped inside the full package.
- No `__pycache__`, `.pyc`, or `.pyo` files are shipped.
- `verification/screenshots/` contains only the current repair proof set.
- `Worlds/verification/screenshots/` is not used as a stale screenshot dump in release packages.
- `build_manifest.json`, `Worlds/active_game.json`, `Worlds/mission_index.json`, and `Worlds/mission_registry.json` must reflect the current pass and all active worlds.
- Package checker must fail on nested zips and stale screenshots, not just warn.

## Active worlds

- Mimas Snowfield
- Enceladus Ice
- Iapetus Ridge
- Titan Methane Coast

## Preserve

Pass50 must preserve Pass49 rover/drone controls, signal rescue, flight-drone power, auto-dock recharge, action contracts, progress/result contracts, audio/FX authority, generation rules, Windows settings, and shell UI standards.
