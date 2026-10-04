# Utopia Conflict — Standards Status

Authority: `1.0.18-utopia-conflict-pass55-pause-menu-input-repair`

## Active presentation standards

- Python 3.13.5 / Panda3D 1.10.16 target.
- 1920x1080 bordered default presentation; no OS resolution changes.
- Normal direct launch opens one deploy briefing, not a second gameplay HUD.
- Deploy briefing freezes gameplay and hides HUD, crosshair, and weapon mounts.
- Enter deploys; F1 opens the modal Field Reference; ESC opens true pause/settings.
- Pause/settings has visible selection and must remain usable by W/S, Up/Down, Enter/Space, mouse, and Esc resume.
- Normal gameplay HUD remains Pass 52-minimal: Score/Lab plus compact left/right ammo.
- World-space geometry owns capture, district, and travel guidance.
- New features do not automatically receive persistent HUD panels.
- F1 is the player help/reference authority and must reflect actual controls and game semantics.
- Enemy semantic colors and six weapon signatures remain gameplay-readable.
- Four field activities remain district-authored: two Calibration, one High Towers, one Pyramid Sector.
- Procedural streaming remains budgeted at 3 generated chunks per stream tick.
- Source Vector Arena authority remains `Vector Arena/standalone_native_adapter.py`.
- Root discovery metadata must agree across build manifest, standalone manifest, mission index, README, and validation.
- Full package ships without `__pycache__`, `.pyc`, runtime logs, crash carryover, or stale active screenshots.

## Pass 55 hard contract

`--pause-menu-input-test` requires:

- ESC opens pause/settings
- Down navigation visibly selects Draw Distance
- Enter activates the selected setting without closing the menu
- Up navigation returns to Resume
- Enter resumes gameplay
- five menu actions remain present

## Pass 54 preserved contract

`--presentation-readiness-test` requires:

- launch briefing visible
- player and spawn timer frozen before deployment
- gameplay HUD and crosshair hidden
- first-person weapon mounts hidden
- F1 reference opens from launch and returns to launch
- Deploy enters gameplay
- standalone manifest identifies F1 as help and H as HUD
- manifest activity locations match Calibration / High Towers / Pyramid Sector

Pass 51 mastering, Pass 52 HUD minimalism, and Pass 53 help-reference contracts remain mandatory regressions.
