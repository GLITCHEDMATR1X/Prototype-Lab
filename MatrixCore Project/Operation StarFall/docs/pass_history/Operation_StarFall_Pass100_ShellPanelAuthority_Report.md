# Operation StarFall Pass100 — Shell Panel Authority

Base: Pass99 Modal Authority Candidate.
Primary target: StarFall shell pause/map/help ownership, readability, and 16:9 safe-canvas compliance.
Frozen systems: Pass99 embedded moon modal ownership, operation transition isolation, operation results/credits flow, moon-world gameplay.

## Previous-pass recheck
- Mimas embedded options open/close/reopen/TAB-return regression: PASS.
- Mimas -> ship -> Enceladus -> ship cycle: PASS.
- Embedded cleanup residue after return: 0 render roots / 0 UI roots.

## Reproduced shell defects
- World-space labels such as `ARCHIVE BOT` remained visible behind shell panels.
- Help contained developer-facing copy about debug panels and the safe canvas.
- Saturn map right detail panel/buttons exceeded the documented safe-canvas boundary.
- Help text was too small at the exact 1280x720 minimum.
- The prior shell authority test only checked the map backdrop, allowing child controls to violate the safe canvas while the test still passed.

## Repair
- Shell panels snapshot/hide normal interior world labels and restore their previous visibility when closed.
- Added a direct shell-panel exclusivity probe covering pause/map/help, HUD suppression, world-label suppression, and cursor ownership.
- Removed developer/debug/safe-canvas copy from player-facing help.
- Increased pause/help panel opacity and simplified pause subtitle to `SHIP SYSTEMS`.
- Shortened map intro and mission-detail copy.
- Repositioned/resized map detail panel, preview, launch and back controls inside the safe canvas.
- Enlarged help text for 1280x720.
- Strengthened shell authority QA to verify real control bounds and world-label restoration, not a hard-coded PASS.

## Runtime evidence
Panda3D 1.10.16 / Python 3.13.5, Linux offscreen runtime.
- Pause, map and help captured and visually inspected at exact 1280x720: PASS.
- Saturn map captured and visually inspected at 1920x1080: PASS.
- Shell authority contract including close/restore behavior: PASS.
- Pass99 Mimas return-controls regression: PASS.
- Pass99 Mimas -> Enceladus operation-cycle regression: PASS.
- Clean preverification ZIP extracted into a blank directory: PASS.
- Shell authority, exact 1280x720 map capture, Mimas return-controls, and the two-operation cycle reproduced from that extracted package: PASS.
- Package hygiene remained clean after runtime with bytecode writes disabled: PASS.

Windows/native-GPU player validation remains pending. Status is CANDIDATE, not accepted authority.
