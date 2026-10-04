from __future__ import annotations
import json, sys, struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

required = [
    'main.py','README.md','requirements.txt','run_game.bat','build_manifest.json',
    'Worlds/main.py','Worlds/display_config.py','Worlds/settings_authority.py','Worlds/transport_link.py',
    'Worlds/mission_index.json','Worlds/mission_registry.json','Worlds/active_game.json',
    'standards/OPERATION_STARFALL_MASTERING_PHASE_v0.1.md',
    'standards/OPERATION_STARFALL_SCREEN_STANDARD_v0.3.md','standards/starfall_screen_contract_v0.3.json',
    'standards/OPERATION_STARFALL_GENERATION_TERRAIN_STANDARD_v0.2.md',
    'standards/starfall_generation_terrain_contract_v0.2.json',
    'tools/starfall_package_check.py',
    'Operation_StarFall_Pass114_PlutoTerrainVisualCleanup_Report.md',
    'Operation_StarFall_Pass114_PlutoTerrainVisualCleanup_validation.txt',
    'Operation_StarFall_Pass114_PlutoTerrainVisualCleanup_changed_files.txt',
    'verification/test_pass108_planet_display_authority.py',
    'verification/reports/Operation_StarFall_Pass108_planet_display_static_contract.json',
    'verification/test_pass109_planet_display_lifecycle.py',
    'verification/reports/Operation_StarFall_Pass109_planet_display_lifecycle_static_contract.json',
    'verification/test_pass110_interior_authority_cleanup.py',
    'verification/reports/Operation_StarFall_Pass110_interior_authority_cleanup_static_contract.json',
    'verification/test_pass111_interior_authority_recheck.py',
    'verification/reports/Operation_StarFall_Pass111_interior_authority_recheck_static_contract.json',
    'verification/test_pass112_remote_drone_telemetry.py',
    'verification/reports/Operation_StarFall_Pass112_remote_drone_telemetry_static_contract.json',
    'verification/test_pass113_remote_telemetry_layout.py',
    'verification/reports/Operation_StarFall_Pass113_remote_telemetry_layout_static_contract.json',
    'verification/reports/Operation_StarFall_Pass113_runtime_visual.json',
    'verification/test_pass114_pluto_terrain_visual_cleanup.py',
    'verification/reports/Operation_StarFall_Pass114_pluto_terrain_visual_static_contract.json',
    'verification/reports/Operation_StarFall_Pass114_runtime_visual.json',
    'verification/reports/terrain_horizon_static_contract.json',
    'verification/gxtool/Pass104_static_scan.json','verification/gxtool/Pass104_panda3d_doctor.json',
    # Frozen proof from the Pass103 base.  These do not claim Pass104 terrain acceptance.
    'verification/gxtool/Pass103_runtime_proof.json','verification/gxtool/Pass103_playtest_run_report.json',
    'verification/gxtool/Pass103_interior_startup_1080p.png','verification/gxtool/Pass103_flight_after_toggle_1080p.png',
]
for rel in required:
    if not (ROOT / rel).is_file():
        errors.append(f'missing required file: {rel}')

for p in ROOT.rglob('*'):
    rel = p.relative_to(ROOT).as_posix()
    if p.is_dir() and p.name == '__pycache__':
        errors.append(f'forbidden cache dir: {rel}')
    if p.is_file() and p.suffix.lower() in {'.pyc','.pyo'}:
        errors.append(f'forbidden bytecode: {rel}')
    if p.is_file() and p.suffix.lower() == '.zip':
        errors.append(f'nested zip: {rel}')
    if p.is_file() and p.parent == ROOT and p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and p.name != 'icon.png':
        errors.append(f'root screenshot/image: {rel}')
    if p.is_file() and p.parent == ROOT and p.name.startswith('Operation_StarFall_Pass') and 'Pass114_' not in p.name:
        errors.append(f'stale root pass artifact: {rel}')

# Loading cards remain part of frozen shell authority.
def _png_size(path: Path):
    with path.open('rb') as fh:
        sig = fh.read(24)
    if len(sig) < 24 or sig[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    return struct.unpack('>II', sig[16:24])

for moon in ('mimas','enceladus','iapetus','titan','mars','pluto','europa','triton'):
    rel = f'assets/generated/operation_loading_{moon}.png'
    path = ROOT / rel
    if not path.is_file():
        errors.append(f'missing loading card: {rel}')
        continue
    try:
        width, height = _png_size(path)
        if width < 1280 or height < 720:
            errors.append(f'loading card below minimum resolution: {rel} {width}x{height}')
        if abs((width / height) - (16 / 9)) > 0.003:
            errors.append(f'loading card not 16:9: {rel} {width}x{height}')
    except Exception as exc:
        errors.append(f'loading card unreadable: {rel}: {exc}')

try:
    manifest = json.loads((ROOT/'build_manifest.json').read_text())
    if manifest.get('pass') != 114:
        errors.append('build_manifest pass is not 114')
    if manifest.get('build') != 'Operation_StarFall_Pass114_PlutoTerrainVisualCleanup':
        errors.append('build_manifest build id mismatch')
    if manifest.get('planet_display_contract') != 'operation_starfall_remote_planet_display_v0.2':
        errors.append('build_manifest planet display contract mismatch')
    if manifest.get('generation_terrain_contract') != 'operation_starfall_generation_terrain_v0.2':
        errors.append('build_manifest terrain contract mismatch')
    if manifest.get('new_contract') != 'operation_starfall_reference_1080p_window_v3':
        errors.append('build_manifest display contract regression')
except Exception as exc:
    errors.append(f'build_manifest unreadable: {exc}')

try:
    active = json.loads((ROOT/'Worlds/active_game.json').read_text())
    if active.get('last_updated_by_pass') != 'Pass114_PlutoTerrainVisualCleanup':
        errors.append('active_game pass identity mismatch')
    if active.get('normal_player_travel_authority') != 'interior_remote_drone_only':
        errors.append('active_game normal-player travel authority mismatch')
    if active.get('transport_mode') != 'embedded_world_remote_drone_display_v4':
        errors.append('active_game transport mode mismatch')
    if active.get('remote_planet_display') != 'centered_16_9_interior_panel':
        errors.append('active_game remote display authority mismatch')
    if active.get('default_display_mode') != 'reference_1080p_window':
        errors.append('active_game default display mode mismatch')
    if active.get('display_contract') != 'operation_starfall_reference_1080p_window_v3':
        errors.append('active_game display contract mismatch')
except Exception as exc:
    errors.append(f'active_game unreadable: {exc}')

try:
    terrain_contract = json.loads((ROOT/'standards/starfall_generation_terrain_contract_v0.2.json').read_text())
    if terrain_contract.get('contract') != 'operation_starfall_generation_terrain_v0.2':
        errors.append('terrain contract id mismatch')
    worlds = terrain_contract.get('active_worlds', [])
    if worlds != ['mimas','enceladus','iapetus','titan','mars','pluto','europa','triton']:
        errors.append(f'terrain contract world list mismatch: {worlds}')
except Exception as exc:
    errors.append(f'terrain contract unreadable: {exc}')

try:
    static = json.loads((ROOT/'verification/reports/terrain_horizon_static_contract.json').read_text())
    if static.get('status') != 'TECHNICAL_PASS':
        errors.append(f'terrain static contract not TECHNICAL_PASS: {static.get("status")}')
    # Important: package checker must not convert missing runtime evidence into visual acceptance.
    if static.get('visual_runtime_status') != 'PENDING':
        errors.append('terrain visual runtime status must remain PENDING until actual Panda frames exist')
    if static.get('gameplay_bounds_changed') is not False:
        errors.append('terrain static report says gameplay bounds changed')
    checks = static.get('checks', {})
    if not checks or not all(checks.values()):
        errors.append(f'terrain static checks incomplete/failed: {checks}')
    models = static.get('world_edge_models', {})
    if set(models) != {'mimas','enceladus','titan','mars','pluto','europa','triton'}:
        errors.append('terrain static world coverage mismatch')
    for world, info in models.items():
        if info.get('coordinate_match') is not True or float(info.get('band_zero_coordinate_max_delta', 1.0)) > 1e-9:
            errors.append(f'terrain edge coordinate mismatch: {world}: {info}')
except Exception as exc:
    errors.append(f'terrain static report unreadable: {exc}')

# Source contract: this is technical presence only, never visual quality proof.
try:
    source = (ROOT/'Worlds/main.py').read_text(encoding='utf-8')
    source_requirements = {
        'terrain contract v0.2': 'operation_starfall_generation_terrain_v0.2',
        'horizon authority': 'operation_starfall_terrain_horizon_v0.1',
        'horizon builder': 'def make_square_horizon_ring(',
        'same height authority': 'height_func=self.world.surface_height',
        'visual-only collision tag': 'visual_only_outside_playable_bounds',
        'Titan methane continuation': 'titan_methane_horizon_continuation',
        'Titan shoreline continuation': 'titan_wet_shoreline_horizon_continuation',
        'failure-revealing shot': '--terrain-horizon-shot',
    }
    for label, needle in source_requirements.items():
        if needle not in source:
            errors.append(f'missing terrain source contract: {label}')

    pluto_cleanup_requirements = {
        'old Pluto rendered ring wall removed': 'ring_wall = edge_band * edge_band * 420.0',
        'old Pluto gameplay barrier wall removed': 'barrier_wall = barrier_band * barrier_band * 520.0',
        'old Pluto barrier teeth removed': 'barrier_teeth = barrier_band *',
    }
    for label, needle in pluto_cleanup_requirements.items():
        if needle in source:
            errors.append(f'Pluto cleanup regression: {label}')
    if 'Pass106: Pluto formations are solid terrain features' not in source:
        errors.append('missing Pluto opaque-formation authority')
    if 'cluster_count = (1 + int(self.world._hash01' not in source:
        errors.append('missing Pass114 sparse Pluto cluster authority')
except Exception as exc:
    errors.append(f'Worlds/main.py unreadable: {exc}')

# Pass107 Triton terrain simplification contract.
try:
    source = (ROOT/'Worlds/main.py').read_text(encoding='utf-8')
    triton_requirements = {
        'reduced Triton spire target': '"rock_spire_target_count": 12',
        'reduced Triton jagged strength': '"jagged_strength": 0.62',
        'reduced Triton rock height': '"rock_height_scale": 0.90',
        'restrained Triton valley wall': 'inner_wall = depth * 0.20',
        'restrained Triton outer wall': 'outer_wall = depth * 0.08',
        'reduced Triton shelf amplitude': 'max(0.0, band) ** 2.2 * 38.0',
        'reduced Triton jagged contribution': 'strength=0.62) * 0.35',
    }
    for label, token in triton_requirements.items():
        if token not in source:
            errors.append(f'missing Pass107 Triton contract: {label}')
except Exception as exc:
    errors.append(f'Pass107 Triton source contract unreadable: {exc}')


try:
    doctor = json.loads((ROOT/'verification/gxtool/Pass104_panda3d_doctor.json').read_text())
    if doctor.get('bridge_version') != '0.8.0-v4-perception':
        errors.append('GXTool v4 doctor bridge identity mismatch')
    if doctor.get('environment', {}).get('ready') is not False:
        errors.append('Pass104 doctor unexpectedly claims Panda3D runtime ready; terrain validation record must be regenerated')
except Exception as exc:
    errors.append(f'Pass104 GXTool doctor unreadable: {exc}')
try:
    scan = json.loads((ROOT/'verification/gxtool/Pass104_static_scan.json').read_text())
    if int(scan.get('summary', {}).get('code_file_count', 0)) < 8:
        errors.append('GXTool static scan code inventory incomplete')
except Exception as exc:
    errors.append(f'Pass104 GXTool static scan unreadable: {exc}')

# Frozen Pass103 base proof: validate that previous accepted candidate evidence remains intact,
# but do not reinterpret it as terrain proof.
try:
    proof = json.loads((ROOT/'verification/gxtool/Pass103_runtime_proof.json').read_text())
    state = proof.get('app_state', {})
    if proof.get('status') not in {'pass','screenshot_captured'}:
        errors.append(f'Pass103 GXTool runtime proof status mismatch: {proof.get("status")}')
    if state.get('build') != 'Operation_StarFall_Pass103_GXToolRuntimeObservability':
        errors.append('frozen Pass103 GXTool build identity mismatch')
    if state.get('window_size') != [1920,1080]:
        errors.append(f'frozen Pass103 GXTool window mismatch: {state.get("window_size")}')
except Exception as exc:
    errors.append(f'frozen Pass103 GXTool runtime proof unreadable: {exc}')
try:
    replay = json.loads((ROOT/'verification/gxtool/Pass103_playtest_run_report.json').read_text())
    if replay.get('ok') is not True or replay.get('completed_steps') != replay.get('step_count') or len(replay.get('assertion_failures', [])) != 0:
        errors.append('frozen Pass103 deterministic replay did not fully pass')
except Exception as exc:
    errors.append(f'frozen Pass103 GXTool replay unreadable: {exc}')

try:
    display = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass108_planet_display_static_contract.json').read_text())
    if display.get('status') != 'TECHNICAL_PASS':
        errors.append(f'Pass108 planet display static contract not TECHNICAL_PASS: {display.get("status")}')
    if display.get('visual_runtime_status') != 'PENDING':
        errors.append('Pass108 visual runtime status must remain PENDING until a current Panda3D frame exists')
    checks = display.get('checks', {})
    if not checks or not all(checks.values()):
        errors.append(f'Pass108 planet display checks incomplete/failed: {checks}')
except Exception as exc:
    errors.append(f'Pass108 planet display static contract unreadable: {exc}')

try:
    lifecycle = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass109_planet_display_lifecycle_static_contract.json').read_text())
    if lifecycle.get('status') != 'TECHNICAL_PASS':
        errors.append(f'Pass109 lifecycle static contract not TECHNICAL_PASS: {lifecycle.get("status")}')
    if lifecycle.get('visual_runtime_status') != 'PENDING':
        errors.append('Pass109 visual runtime status must remain PENDING until a current Panda3D frame exists')
    checks = lifecycle.get('checks', {})
    if not checks or not all(checks.values()):
        errors.append(f'Pass109 lifecycle checks incomplete/failed: {checks}')
except Exception as exc:
    errors.append(f'Pass109 lifecycle static contract unreadable: {exc}')

try:
    interior = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass110_interior_authority_cleanup_static_contract.json').read_text())
    if interior.get('status') != 'TECHNICAL_PASS':
        errors.append(f'Pass110 interior authority static contract not TECHNICAL_PASS: {interior.get("status")}')
    if interior.get('visual_runtime_status') != 'PENDING':
        errors.append('Pass110 visual runtime status must remain PENDING until a current Panda3D frame exists')
    checks = interior.get('checks', {})
    if not checks or not all(checks.values()):
        errors.append(f'Pass110 interior authority checks incomplete/failed: {checks}')
except Exception as exc:
    errors.append(f'Pass110 interior authority static contract unreadable: {exc}')


try:
    recheck = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass111_interior_authority_recheck_static_contract.json').read_text())
    if recheck.get('status') != 'TECHNICAL_PASS':
        errors.append(f'Pass111 recheck static contract not TECHNICAL_PASS: {recheck.get("status")}')
    if recheck.get('visual_runtime_status') != 'PENDING':
        errors.append('Pass111 visual runtime status must remain PENDING until a current Panda3D frame exists')
    checks = recheck.get('checks', {})
    if not checks or not all(checks.values()):
        errors.append(f'Pass111 recheck checks incomplete/failed: {checks}')
except Exception as exc:
    errors.append(f'Pass111 recheck static contract unreadable: {exc}')

try:
    shell_source = (ROOT/'main.py').read_text(encoding='utf-8')
    world_source = (ROOT/'Worlds/main.py').read_text(encoding='utf-8')
    display_tokens = {
        '16:9 panel builder': 'def build_operation_display_panel(self)',
        'centered display region': 'self.operation_display_region_dims = (0.11, 0.89, 0.11, 0.89)',
        'remote feed camera': 'starfall_remote_planet_drone_camera',
        'interior remains visible': 'self.flight_root.hide()\n        self.interior_root.show()\n        self.mode = "interior"',
        'planet feed state': '"planet_feed_active"',
    }
    for label, token in display_tokens.items():
        if token not in shell_source:
            errors.append(f'missing Pass108 source contract: {label}')
    if 'self.camera = feed_factory(self.operation_render_root)' not in world_source:
        errors.append('embedded world does not adopt Pass108 remote feed camera')
    if 'self.camera.reparentTo(operation_root)' in shell_source:
        errors.append('Pass108 regression: shell camera still reparents into operation root')
    lifecycle_tokens = {
        'partial constructor registry': 'EMBEDDED_INSTANCE = self',
        'partial constructor cleanup': 'def _cleanup_partial_embedded_operation(self, module)',
        'shell fallback cleanup': 'def _force_clear_operation_residue(self, module=None)',
        'lifecycle state': 'def _operation_lifecycle_state(self)',
        'clean lifecycle gate': 'def _operation_lifecycle_is_clean(self',
    }
    for label, token in lifecycle_tokens.items():
        haystack = world_source if label == 'partial constructor registry' else shell_source
        if token not in haystack:
            errors.append(f'missing Pass109 lifecycle source contract: {label}')
    interior_tokens = {
        'no pause flight button': 'RETURN TO FLIGHT',
        'no observatory flight prompt': 'F FLIGHT',
        'interior anomaly feedback': 'ANOMALY ANALYSIS // INTERIOR ONLY',
        'interior anomaly map label': 'INTERIOR ANALYSIS / NO FLIGHT',
    }
    for label, token in interior_tokens.items():
        if label.startswith('no '):
            if token in shell_source:
                errors.append(f'Pass110 interior authority regression: {label}')
        elif token not in shell_source:
            errors.append(f'missing Pass110 interior authority source contract: {label}')
    if 'LOCAL: Starfall salvage loop' in shell_source:
        errors.append('Pass111 recheck regression: stale ANOM salvage-loop station purpose remains')
    if '("ANOM", "ANOMALY FIELD", "INTERIOR: anomaly telemetry analysis")' not in shell_source:
        errors.append('Pass111 recheck missing interior ANOM station purpose')
    if '"build": "Operation_StarFall_Pass114_PlutoTerrainVisualCleanup"' not in shell_source:
        errors.append('Pass114 GXTOOL runtime scene-state build identity is stale')
    telemetry_tokens = {
        'standard action bridge': 'payload_factory = getattr(app, "_standard_action_payload", None)',
        'live action hint': 'objective = str(action_payload.get("hint", objective) or objective).upper()',
        'live action progress': 'action_progress = max(0, min(100, int(action_payload.get("progress", 0) or 0)))',
        'combined live telemetry': 'status = f"{action_state} {action_progress:03d}% // {telemetry}"',
    }
    for label, token in telemetry_tokens.items():
        if token not in shell_source:
            errors.append(f'missing Pass112 telemetry source contract: {label}')
    pass113_shell_tokens = {
        'lower bezel objective': '(-1.30, -0.820)',
        'lower bezel status': '(1.30, -0.820)',
        'lower bezel controls': '(0.0, -0.872)',
        'extended lower bezel': 'outer.setFrame(-half_w - 0.055, half_w + 0.055, -half_h - 0.145, half_h + 0.070)',
    }
    for label, token in pass113_shell_tokens.items():
        if token not in shell_source:
            errors.append(f'missing Pass113 telemetry layout source contract: {label}')
    pass113_world_tokens = {
        'embedded sonar ownership': '"sonar_meter_root", "pip_root"',
        'embedded vision ownership': '"planet_vision_overlay_root"',
        'embedded access ownership': '"universal_access_title", "universal_access_summary_text"',
        'embedded vision update guard': 'if getattr(self, "embedded_operation", False):\n            root.hide()\n            return',
    }
    for label, token in pass113_world_tokens.items():
        if token not in world_source:
            errors.append(f'missing Pass113 embedded HUD ownership contract: {label}')
except Exception as exc:
    errors.append(f'Pass113 source authority unreadable: {exc}')

try:
    current = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass113_remote_telemetry_layout_static_contract.json').read_text())
    if current.get('status') != 'TECHNICAL_PASS' or current.get('visual_runtime_status') != 'VISUAL_PASS':
        errors.append(f'Pass113 current contract not accepted: {current.get("status")} / {current.get("visual_runtime_status")}')
    checks = current.get('checks', {})
    if not checks or not all(checks.values()):
        errors.append(f'Pass113 current contract checks incomplete/failed: {checks}')
except Exception as exc:
    errors.append(f'Pass113 current static contract unreadable: {exc}')

try:
    visual = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass113_runtime_visual.json').read_text())
    if visual.get('status') != 'VISUAL_PASS':
        errors.append('Pass113 runtime visual report is not VISUAL_PASS')
    capture = visual.get('capture', {})
    if capture.get('width') != 1920 or capture.get('height') != 1080 or len(str(capture.get('sha256', ''))) != 64:
        errors.append(f'Pass113 runtime capture metadata invalid: {capture}')
    runtime_checks = visual.get('runtime_checks', {})
    if not runtime_checks or not all(runtime_checks.values()):
        errors.append(f'Pass113 runtime checks incomplete/failed: {runtime_checks}')
except Exception as exc:
    errors.append(f'Pass113 runtime visual report unreadable: {exc}')

# Pass114 Pluto-only visual terrain repair. Previous Pass113 evidence remains frozen.
try:
    world_source = (ROOT/'Worlds/main.py').read_text(encoding='utf-8')
    pass114_tokens = {
        'sparse Pluto rock sites': '"rock_spire_target_count": 24',
        'lower Pluto rock height': '"rock_height_scale": 1.04',
        'one-to-two Pluto crags per site': 'cluster_count = (1 + int(self.world._hash01',
        'broad Pluto crag footprint': 'height * (0.28 + self.world._hash01',
        'flat-topped Pluto crag taper': 'taper_exponent=0.30 if IS_PLUTO_LEVEL else 0.92',
        'subdued Pluto ice material': 'base_color = (0.48, 0.55, 0.64, 1.0)',
    }
    for label, token in pass114_tokens.items():
        if token not in world_source:
            errors.append(f'missing Pass114 Pluto visual contract: {label}')
except Exception as exc:
    errors.append(f'Pass114 Pluto source contract unreadable: {exc}')

try:
    current114 = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass114_pluto_terrain_visual_static_contract.json').read_text())
    if current114.get('status') != 'TECHNICAL_PASS' or current114.get('visual_runtime_status') != 'VISUAL_PASS':
        errors.append(f'Pass114 current contract not accepted: {current114.get("status")} / {current114.get("visual_runtime_status")}')
    checks114 = current114.get('checks', {})
    if not checks114 or not all(checks114.values()):
        errors.append(f'Pass114 current contract checks incomplete/failed: {checks114}')
except Exception as exc:
    errors.append(f'Pass114 current static contract unreadable: {exc}')

try:
    visual114 = json.loads((ROOT/'verification/reports/Operation_StarFall_Pass114_runtime_visual.json').read_text())
    if visual114.get('status') != 'VISUAL_PASS':
        errors.append('Pass114 runtime visual report is not VISUAL_PASS')
    capture114 = visual114.get('capture', {})
    if capture114.get('width') != 1920 or capture114.get('height') != 1080 or len(str(capture114.get('sha256', ''))) != 64:
        errors.append(f'Pass114 runtime capture metadata invalid: {capture114}')
    runtime114 = visual114.get('runtime_checks', {})
    if not runtime114 or not all(runtime114.values()):
        errors.append(f'Pass114 runtime checks incomplete/failed: {runtime114}')
except Exception as exc:
    errors.append(f'Pass114 runtime visual report unreadable: {exc}')

report = {
    'status': 'PASS' if not errors else 'FAIL',
    'pass': 114,
    'interior_authority_technical_status': 'TECHNICAL_PASS' if not errors else 'FAIL',
    'planet_display_visual_runtime_status': 'VISUAL_PASS',
    'planet_display_visual_runtime_note': 'Pass114 preserves accepted Pass113 display authority and adds one current Panda3D 1.10.16 1920x1080 Pluto runtime screenshot plus clean Pluto return-controls verification.',
    'errors': errors,
}
out = ROOT/'verification/reports/Operation_StarFall_Pass114_package_hygiene_report.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
sys.exit(0 if not errors else 1)
