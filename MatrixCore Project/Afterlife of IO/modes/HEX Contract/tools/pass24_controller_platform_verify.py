"""Pass 24 controller/platform readiness verifier. Does not import pygame."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/mnt/data/hex_pass24_base/HEX Contract')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    app = (ROOT / 'game/app.py').read_text(encoding='utf-8')
    render = (ROOT / 'game/render.py').read_text(encoding='utf-8')
    req = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    controller_source = (ROOT / 'game/platform_input.py').read_text(encoding='utf-8')
    save_source = (ROOT / 'game/save_paths.py').read_text(encoding='utf-8')
    mapping = json.loads((ROOT / 'platform/xbox/controller_mapping.json').read_text(encoding='utf-8'))

    input_mod = load_module(ROOT / 'game/platform_input.py', 'hex_platform_input')
    save_mod = load_module(ROOT / 'game/save_paths.py', 'hex_save_paths')

    checks = {}
    checks['pygame_ce_pinned'] = 'pygame-ce==2.5.7' in req
    checks['normalized_sdl2_controller_layer'] = 'pygame._sdl2' in app and 'sdl_controller.Controller' in app and 'set_eventstate(True)' in app
    checks['xbox_buttons_mapped'] = all(token in app for token in (
        'CONTROLLER_BUTTON_A', 'CONTROLLER_BUTTON_B', 'CONTROLLER_BUTTON_X', 'CONTROLLER_BUTTON_Y',
        'CONTROLLER_BUTTON_START', 'CONTROLLER_BUTTON_BACK', 'CONTROLLER_BUTTON_LEFTSHOULDER',
        'CONTROLLER_BUTTON_RIGHTSHOULDER', 'CONTROLLER_BUTTON_DPAD_UP', 'CONTROLLER_BUTTON_DPAD_DOWN',
        'CONTROLLER_BUTTON_DPAD_LEFT', 'CONTROLLER_BUTTON_DPAD_RIGHT'))
    checks['left_stick_navigation'] = all(token in app for token in ('CONTROLLER_AXIS_LEFTX', 'CONTROLLER_AXIS_LEFTY', 'axis_latch', '18000', '9500'))
    checks['hotplug_connect_disconnect'] = all(token in app for token in ('CONTROLLERDEVICEADDED', 'CONTROLLERDEVICEREMOVED', '_open_controller', '_remove_controller'))
    checks['disconnect_pauses_active_contract'] = 'XBOX CONTROLLER' not in app and 'Xbox Controller DISCONNECTED / GAME PAUSED' in app and 'self.paused = True' in app
    checks['focus_loss_checkpoint_pause'] = all(token in app for token in ('WINDOWFOCUSLOST', 'WINDOWMINIMIZED', '_checkpoint("focus_lost")', 'FOCUS LOST / CONTRACT PAUSED'))
    checks['focus_restore_no_auto_resume'] = 'WINDOWFOCUSGAINED' in app and 'PRESS MENU OR SPACE TO RESUME' in app
    checks['keyboard_mouse_fallback_preserved'] = 'pygame.KEYDOWN' in app and 'pygame.MOUSEBUTTONDOWN' in app and '_set_input_mode(INPUT_KEYBOARD)' in app
    checks['controller_prompt_switching'] = 'draw_platform_prompt' in render and 'INPUT_XBOX' in render and 'prompt_for' in render
    checks['active_mission_prompt_nonoverlap'] = 'mission_active and not paused and not notice' in render
    checks['menu_focus_title'] = 'selected_index' in render and 'self.title_index' in app
    checks['restore_focus'] = 'selected_hero' in render and 'self.restore_index' in app
    checks['bond_focus'] = 'self.bond_index' in app and 'selected_index: int = 0' in render
    checks['sidekick_controller_combos'] = '_cycle_sidekick_combo' in app and 'combinations(candidates, count)' in app
    checks['all_menu_states_have_controller_logic'] = all(state in app for state in (
        '"TITLE"', '"SETTINGS"', '"CONTRACT_BOARD"', '"HERO_SELECT"', '"LOADOUT_PREP"',
        '"RESTORE_SELECT"', '"LAST_LIGHT"', '"BOND_EVENT"', '"MISSION"'))
    checks['profile_schema_still_v9'] = '"profile_version": 9' in app and 'profile["profile_version"] = 9' in app
    checks['achievement_module_preserved'] = sha(ROOT/'game/achievements.py') == sha(BASE/'game/achievements.py')
    checks['achievement_manifest_preserved'] = sha(ROOT/'platform/xbox/achievements_manifest.json') == sha(BASE/'platform/xbox/achievements_manifest.json')

    frozen = ('main.py','game/data.py','game/sim.py','game/actors.py','game/actor_visuals.py','game/audio.py','game/world_data.py','game/world.py')
    frozen_result = {rel: sha(ROOT/rel) == sha(BASE/rel) for rel in frozen}
    checks['gameplay_world_balance_frozen'] = all(frozen_result.values())

    checks['save_root_cli_and_env'] = '--save-root' in app and 'HEX_CONTRACT_SAVE_ROOT' in save_source and 'resolve_profile_path' in app
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / 'project'; project.mkdir()
        legacy = save_mod.resolve_profile_path(project)
        explicit_root = save_mod.resolve_profile_path(project, explicit_root=str(Path(td)/'sync'))
        explicit_profile = save_mod.resolve_profile_path(project, explicit_profile=str(Path(td)/'manual.json'), explicit_root=str(Path(td)/'ignored'))
        old = os.environ.get('HEX_CONTRACT_SAVE_ROOT')
        try:
            os.environ['HEX_CONTRACT_SAVE_ROOT'] = str(Path(td)/'envsync')
            env_path = save_mod.resolve_profile_path(project)
        finally:
            if old is None:
                os.environ.pop('HEX_CONTRACT_SAVE_ROOT', None)
            else:
                os.environ['HEX_CONTRACT_SAVE_ROOT'] = old
        checks['save_root_resolution_contract'] = (
            legacy == project/'save_profile.json' and
            explicit_root == Path(td)/'sync'/'save_profile.json' and
            explicit_profile == Path(td)/'manual.json' and
            env_path == Path(td)/'envsync'/'save_profile.json'
        )

    # Pure logical input layer tests.
    checks['wrap_index_contract'] = input_mod.wrap_index(0,-1,4) == 3 and input_mod.wrap_index(3,1,4) == 0
    required_prompts = ('TITLE','SETTINGS','CONTRACT_BOARD','HERO_SELECT','LOADOUT_PREP','RESTORE_SELECT','LAST_LIGHT','BOND_EVENT','MISSION')
    prompts = {state: input_mod.prompt_for(state, mission_finished=(state=='MISSION')).primary for state in required_prompts}
    checks['controller_prompt_contract'] = all(bool(value) for value in prompts.values()) and '[A]' in prompts['TITLE'] and '[A]' in prompts['MISSION']
    checks['official_xbox_controller_term'] = 'Xbox Controller' in app and mapping.get('terminology') == 'Xbox Controller'
    checks['no_stdlib_platform_shadowing'] = not (ROOT/'platform/__init__.py').exists()

    ok = all(checks.values())
    payload = {
        'pass24_controller_platform_readiness': 'PASS' if ok else 'FAIL',
        'checks': checks,
        'frozen_pass23_gameplay_modules': frozen_result,
        'controller_mapping': mapping,
        'pure_prompt_samples': prompts,
        'profile_version': 9,
        'native_runtime_claimed': False,
        'native_gdk_claimed': False,
        'environment_limits': ['pygame-ce unavailable', 'Panda3D unavailable', 'Xbox GDK unavailable'],
    }
    out = ROOT/'verification/reports/pass24_controller_platform.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
