from __future__ import annotations
from pathlib import Path
import hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/mnt/data/hex_pass26_authority/HEX Contract')

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    checks={}
    frozen_files=[
        'game/data.py','game/sim.py','game/actors.py','game/actor_visuals.py','game/audio.py',
        'game/world_data.py','game/world.py','game/achievements.py','game/platform_input.py',
        'game/microsoft_runtime.py','platform/xbox/achievements_manifest.json','platform/xbox/controller_mapping.json',
        'platform/microsoft/native_bridge/HEXContractGDKBridge.cpp','platform/microsoft/package_profile.json',
    ]
    frozen={rel:(ROOT/rel).exists() and (BASE/rel).exists() and sha(ROOT/rel)==sha(BASE/rel) for rel in frozen_files}
    checks['gameplay_world_achievement_controller_gdk_frozen']=all(frozen.values())
    app=(ROOT/'game/app.py').read_text(encoding='utf-8')
    crash=(ROOT/'game/crash_reporter.py').read_text(encoding='utf-8')
    main_src=(ROOT/'main.py').read_text(encoding='utf-8')
    win=(ROOT/'platform/windows/BUILD_WINDOWS_FULL_TITLE.bat').read_text(encoding='utf-8')
    spec=(ROOT/'platform/windows/HEXContract.spec').read_text(encoding='utf-8')
    pkg=json.loads((ROOT/'platform/microsoft/package_profile.json').read_text())
    checks['full_game_not_demo']=pkg.get('product_type')=='full_game' and pkg.get('demo') is False and pkg.get('trial') is False
    checks['profile_schema_v9']='"profile_version": 9' in app and 'profile["profile_version"] = 9' in app
    checks['mission_constructor_guard']='profile_before = copy.deepcopy(self.profile)' in app and 'phase="mission_launch"' in app
    checks['mission_runtime_guard']='phase="mission_update"' in app and 'phase="mission_frame"' in app
    checks['sidekick_rollback']='mission_launch_rollback_saved' in app
    checks['recovery_screen']='CRASH_RECOVERY' in app and '_draw_crash_recovery' in app
    checks['top_level_capture']=main_src.find('bootstrap_crash_reporter') < main_src.find('from game.app import main as app_main') and 'show_native_error' in main_src
    checks['thread_unraisable_hooks']='threading.excepthook' in crash and 'sys.unraisablehook' in crash
    checks['faulthandler_enabled']='faulthandler.enable' in crash and 'all_threads=True' in crash
    checks['native_fault_next_boot_recovery']='previous_native_fault' in crash and 'LATEST_CRASH.txt' in crash
    checks['privacy_redaction']='absolute_user_paths_redacted' in crash and 'automatic_upload' in crash and 'save_contents_included' in crash
    checks['bounded_retention']='MAX_REPORT_SETS = 20' in crash
    checks['windows_builder_pinned']=all(x in (ROOT/'platform/windows/requirements_runtime.txt').read_text() for x in ('pygame-ce==2.5.7','pyinstaller==6.21.0'))
    checks['windows_quick_and_visual_smoke']='--quick-test --no-audio --no-save' in win and '--test-shot' in win and 'pass27_windows_title_smoke.png' in win
    checks['windows_crash_reporter_self_test']='--crash-reporter-test --save-root "%CRASHROOT%"' in win and 'CrashReporterSelfTest=PASS' in win and 'HEX_CONTRACT_crash_*.zip' in win
    checks['runtime_package_still_source_clean']='datas=Tree(str(ROOT / "assets"), prefix="assets")' in spec and all(x not in spec for x in ('verification/screenshots','PASS_REPORT.md','tools/pass'))
    checks['no_cache_residue']=not any(p.name=='__pycache__' or p.suffix=='.pyc' for p in ROOT.rglob('*'))
    ok=all(checks.values())
    payload={'pass27_full_regression':'PASS' if ok else 'FAIL','checks':checks,'frozen_files':frozen,'profile_version':9,'product_type':'full_game'}
    out=ROOT/'verification/reports/pass27_full_regression.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps(payload,indent=2)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
