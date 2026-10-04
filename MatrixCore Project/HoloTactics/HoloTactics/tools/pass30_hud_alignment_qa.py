from __future__ import annotations

from pathlib import Path

from holotactics_ui_layout import UI_FRAMES, UI_TEXT_POS, UI_TEXT_SCALE, validate_ui_layout

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8')

checks: list[tuple[str, bool]] = []

def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))

check('layout validator clean', not validate_ui_layout())
check('left panels share outer edge', UI_FRAMES['ui_squad_glass'][0] == UI_FRAMES['ui_help_glass'][0])
check('right panels share inner edge', UI_FRAMES['ui_mission_glass'][0] == UI_FRAMES['ui_comms_glass'][0])
check('right panels share outer edge', UI_FRAMES['ui_mission_glass'][1] == UI_FRAMES['ui_comms_glass'][1])
check('title centered', UI_TEXT_POS['title'][0] == 0.0 and UI_TEXT_POS['subtitle'][0] == 0.0)
check('squad anchor inside panel', UI_FRAMES['ui_squad_glass'][0] < UI_TEXT_POS['squad'][0] < UI_FRAMES['ui_squad_glass'][1])
check('mission anchor inside panel', UI_FRAMES['ui_mission_glass'][0] < UI_TEXT_POS['mission'][0] < UI_FRAMES['ui_mission_glass'][1])
check('comms anchor inside panel', UI_FRAMES['ui_comms_glass'][0] < UI_TEXT_POS['comms'][0] < UI_FRAMES['ui_comms_glass'][1])
check('help anchor inside panel', UI_FRAMES['ui_help_glass'][0] < UI_TEXT_POS['help'][0] < UI_FRAMES['ui_help_glass'][1])
check('720p body scales preserved', min(UI_TEXT_SCALE[k] for k in ('squad','mission','comms','help')) >= 0.033)
check('F9 bound standalone and hosted', MAIN.count('\"f9\": self._toggle_dev_view') >= 2)
check('developer view hidden by default', 'self.dev_view = False' in MAIN and 'self.dev_root.hide()' in MAIN)
update = MAIN[MAIN.index('    def _update_hud'):MAIN.index('    def _wrapped_objective')]
check('player HUD omits threat diagnostic', 'Threat ' not in update)
check('player HUD omits sync percentages', 'Sector Sync' not in update and 'Journey Sync' not in update)
check('player HUD omits audio diagnostics', 'SFX ' not in update and 'MUSIC ' not in update)
check('developer view owns diagnostics', all(token in MAIN[MAIN.index('    def _update_dev_view'):MAIN.index('    def _screen_tile_from_ndc')] for token in ('Threat', 'Sector Sync', 'Journey Sync', 'Audio')))

passed = sum(ok for _, ok in checks)
for name, ok in checks:
    print(('PASS' if ok else 'FAIL'), name)
print(f'Pass 30 HUD alignment QA: {passed}/{len(checks)} PASS')
raise SystemExit(0 if passed == len(checks) else 1)
