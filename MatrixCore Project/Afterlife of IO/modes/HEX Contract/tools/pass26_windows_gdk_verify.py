"""Pass 26 Windows runtime/native GDK readiness verifier. No pygame/GDK import required."""
from __future__ import annotations
from pathlib import Path
import hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/mnt/data/hex_pass25_base_exact/HEX Contract')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 checks={}
 p=json.loads((ROOT/'platform/microsoft/package_profile.json').read_text())
 checks['full_game_mode']=p['product_type']=='full_game' and p['demo'] is False and p['trial'] is False
 checks['current_gdk_x64_label']=p['target']=='x64' and 'simplified' in p['gdk_layout'].lower()
 win=(ROOT/'platform/windows/BUILD_WINDOWS_FULL_TITLE.bat').read_text()
 spec=(ROOT/'platform/windows/HEXContract.spec').read_text()
 checks['windows_builder_pinned']=all(x in (ROOT/'platform/windows/requirements_runtime.txt').read_text() for x in ('pygame-ce==2.5.7','pyinstaller==6.21.0'))
 checks['windows_builder_smoke_test']='--quick-test --no-audio --no-save' in win and 'HEXContract.exe' in win
 checks['windows_builder_visual_smoke']='--test-shot' in win and 'pass26_windows_title_smoke.png' in win and 'VisualSmoke=PASS' in win
 checks['runtime_package_excludes_dev_tree']=all(x not in spec for x in ('verification/screenshots','PASS_REPORT.md','tools/pass')) and 'datas=Tree(str(ROOT / "assets"), prefix="assets")' in spec
 bridge=(ROOT/'platform/microsoft/native_bridge/HEXContractGDKBridge.cpp').read_text()
 for token in ('XGameRuntimeInitialize','XUserAddAsync','XblInitialize','XblContextCreateHandle','XGameSaveFilesGetFolderWithUiAsync','XGameSaveFilesGetFolderWithUiResult','XblAchievementsUpdateAchievementAsync','XblCleanupAsync','XGameRuntimeUninitialize'):
  checks['bridge_'+re.sub(r'[^a-z0-9]+','_',token.lower())]=token in bridge
 build=(ROOT/'platform/microsoft/native_bridge/BUILD_GDK_BRIDGE.bat').read_text()
 checks['bridge_current_x64_layout']='GameDKCoreLatest' in build and 'windows\\lib\\x64' in build and 'Microsoft.Xbox.Services.143.GDK.C.lib' in build
 checks['bridge_partial_init_cleanup']='CleanupUnlocked' in bridge and bridge.count('CleanupUnlocked(); return 0;') >= 5
 adapter=(ROOT/'game/microsoft_runtime.py').read_text()
 checks['python_bridge_optional_fallback']=all(x in adapter for x in ('native_bridge_enabled','PORTABLE','HC_GDK_UpdateAchievement','HC_GDK_RefreshSaveRoot'))
 saves=(ROOT/'game/save_paths.py').read_text()
 checks['frozen_windows_localappdata_fallback']='LOCALAPPDATA' in saves and 'getattr(sys, "frozen", False)' in saves
 app=(ROOT/'game/app.py').read_text()
 checks['app_native_save_before_profile']='MicrosoftRuntime.autodetect' in app and 'platform_save_root' in app and '_refresh_platform_save_root' in app
 checks['app_achievement_sync']='sync_pending(self.microsoft_runtime.update_achievement)' in app
 checks['resume_refresh_hook']='WINDOWRESTORED' in app and 'self._refresh_platform_save_root()' in app
 stage=(ROOT/'tools/pass26_prepare_gdk_stage.py').read_text()
 checks['stage_requires_native_bridge']='HEXContractGDKBridge.dll is required' in stage and "'native_bridge_enabled':True" in stage
 checks['test_package_workflow']=all(x in (ROOT/'platform/microsoft/PASS26_PREPARE_AND_PACK_GDK_TEST.bat').read_text() for x in ('MakePkg genmap','MakePkg pack','/lt','wdapp'))
 accept=(ROOT/'platform/microsoft/native_acceptance/RUN_NATIVE_ACCEPTANCE.ps1').read_text()
 checks['native_acceptance_human_gate']=all(x in accept for x in ('wdapp install','controller_disconnect_safe','achievement_unlock_seen','save_persists_relaunch','offline_reconnect','clean_exit'))
 checks['optional_xgamesaveutil_not_gate']='$optional=' in accept and "$checks['xgamesaveutil_available_for_manual_export']" not in accept
 checks['profile_schema_unchanged']='"profile_version": 9' in app
 frozen=('game/data.py','game/sim.py','game/actors.py','game/actor_visuals.py','game/audio.py','game/world_data.py','game/world.py','platform/xbox/achievements_manifest.json','platform/xbox/controller_mapping.json')
 frozen_result={x:sha(ROOT/x)==sha(BASE/x) for x in frozen}
 checks['gameplay_world_content_frozen']=all(frozen_result.values())
 checks['pass25_achievement_definitions_frozen']=sha(ROOT/'game/achievements.py')==sha(BASE/'game/achievements.py')
 checks['no_cache_residue']=not any(x.name=='__pycache__' or x.suffix=='.pyc' for x in ROOT.rglob('*'))
 ok=all(checks.values())
 out={
  'pass26_windows_full_title_runtime':'PASS' if ok else 'FAIL','checks':checks,'frozen_modules':frozen_result,
  'profile_version':9,'product_type':'full_game','native_windows_exe_claimed':False,'native_gdk_bridge_compiled_claimed':False,
  'native_msixvc_installed_claimed':False,'native_xbox_services_claimed':False,
  'environment_limits':['Windows unavailable','Microsoft GDK unavailable','PyInstaller cannot produce a normal Windows build from this Linux environment','pygame-ce unavailable from configured package mirror','Panda3D unavailable from configured package mirror']
 }
 dest=ROOT/'verification/reports/pass26_windows_gdk_readiness.json'; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(out,indent=2),encoding='utf-8')
 print(json.dumps(out,indent=2)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
