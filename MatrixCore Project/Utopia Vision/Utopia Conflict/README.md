# Utopia Conflict

**Authority:** Pass 55 — Pause Menu Input Repair  
**Version:** `1.0.18-utopia-conflict-pass55-pause-menu-input-repair`  
**Engine target:** Python 3.13.5 / Panda3D 1.10.16

Utopia Conflict is a presentation-ready Prototype Lab hardlight district combat mission. Pass 55 preserves the Pass 54 presentation/gameplay authority and repairs pause/settings so it is fully selectable by keyboard as well as mouse.

## Launch flow

Normal direct launch opens a deploy briefing.

- Enter or **Deploy** — enter city gameplay
- F1 — open the Field Reference before or during city play
- ESC — true pause/settings; includes Quit to Desktop
- Pause menu — W/S or Up/Down selects; Enter/Space activates; mouse remains clickable; ESC resumes

The launch briefing freezes city simulation and hides gameplay HUD, crosshair, and first-person weapon mounts until deployment.

## Core loop

Deploy -> follow physical capture/district cues -> fight with six hardlight weapons -> capture nodes and recover signal objectives -> complete four district field activities -> enter/clear the source Vector Arena route -> earn Lab points -> upgrade -> continue freeroam or return through the mission result contract.

## Controls

- WASD — move
- Mouse — aim/look
- Shift — sprint
- LMB / RMB — fire right / left weapon
- 1–6 — select right weapon
- Shift+1–6 — select left weapon
- Tab / Q — cycle right / left weapon
- E — interact / start nearby field activity / enter available arena portal
- H — toggle the minimal gameplay HUD
- F1 — Field Reference / player help
- F10 — Activity Board
- U — ammo capacity upgrade
- Shift+U — health capacity upgrade
- I — armor shell upgrade
- ESC — true pause/settings
- While paused — W/S or Up/Down selects; Enter/Space activates; mouse remains clickable; ESC resumes

## Field activities

- Calibration District — Core Sample; Imploder Study
- High Towers — Shield Fracture
- Pyramid Sector — Magnet Garden

## Presentation verification

```bash
python -B -m py_compile main.py
python -B main.py --pause-menu-input-test --no-audio
python -B main.py --presentation-readiness-test --no-audio
python -B main.py --mastering-quality-test --no-audio
python -B main.py --hud-minimalism-test --no-audio
python -B main.py --help-reference-test --no-audio
python -B main.py --activity-variety-test --no-audio
python -B main.py --enemy-role-test --no-audio
python -B main.py --enemy-color-state-test --no-audio
python -B main.py --weapon-signature-test --no-audio
python -B main.py --combat-regression-test --no-audio
python -B main.py --capture-regen-test --no-audio
python -B main.py --survivability-test --no-audio
python -B main.py --chunk-smoothing-test --no-audio
python -B main.py --district-activity-test --no-audio
python -B main.py --district-discovery-test --no-audio
python -B main.py --arena-integration-test --no-audio
python -B main.py --standards-check
python -B main.py --mission-contract-test
```

Fresh Pass 55 pause-menu proof is `verification/screenshots/pause_menu_input.png`; Pass 54 presentation proof remains under `verification/screenshots/pass54/`. Prior pass reports are preserved under `docs/history/`.
