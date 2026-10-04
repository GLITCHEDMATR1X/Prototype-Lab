from __future__ import annotations
import ast,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HV=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else None
checks=[]
def check(name,cond,detail=''):
    checks.append((name,bool(cond),detail)); print(f"{'PASS' if cond else 'FAIL'} {name}"+(f" // {detail}" if detail else ''))
def text(p): return p.read_text(encoding='utf-8')
a=text(ROOT/'holoverse_native_adapter.py'); m=json.loads(text(ROOT/'holoverse_mode_manifest.json')); r=json.loads(text(ROOT/'holoverse/holoverse_dimension.json'))
check('real main.py remains source authority',m.get('entry')=='main.py' and m.get('source_entry')=='main.py')
check('native Panda3D manifest',m.get('launch_type')=='native_panda' and m.get('source_kind')=='panda3d')
check('placeholder explicitly forbidden',m.get('placeholder_mode') is False and m.get('performance_contract',{}).get('placeholder_scene') is False)
check('single lifecycle contract',all(m.get('performance_contract',{}).get(k)==0 for k in ('second_showbase','second_window','second_frame_task')))
check('responder promotes same link to native',r.get('compatibility')=='native' and r.get('native_adapter')=='holoverse_native_adapter.py')
check('overlay ships no link UUID',not (ROOT/'.holoverse_link.json').exists())
check('runtime class discovery present','_discover_game_class' in a and 'issubclass(obj,hosted_showbase)' in a and 'class_score' in a)
check('Pass03 ranks real gameplay authority','holoutopia_authority_inventory' in a and 'AUTHORITY_THRESHOLD' in a and 'authority_structural_class' in a)
check('empty bootstrap is explicitly rejected','holoutopia_bootstrap_rejected' in a and 'cleanup_rejected_instance' in a)
check('missing real game fails explicitly','No non-bootstrap HoloUtopia game authority found' in a and 'empty main.py/adapter files' in a)
check('Pass03 recursively scans project tree','project_root.rglob("*.py")' in a and 'authority_structural_class' in a and 'fallback_imports' in a)
check('Pass02 no marker-gated imports','if not strong: continue' not in a and 'source-family mismatch' not in a)
check('standalone run loop suppressed during discovery','def run(self, *args, **kwargs):' in a and 'HoloVerse owns' in a)
check('wrapper-safe source inventory','entry_is_wrapper' in a and 'holoutopia_source_inventory' in a and 'source-family mismatch: missing' not in a)
check('no replacement world geometry',all(tok not in a for tok in ('CardMaker(', 'LineSegs(', 'GeomVertexData(', 'GeomNode(', 'build_hub_infill(', 'update_world_chunks(')))
check('source PRC suppressed','panda_core.loadPrcFileData = lambda *a, **k: None' in a)
check('source PRC restored','_restore_runtime_context' in a and 'loadPrcFileData' in a)
check('single ShowBase','showbase_module.ShowBase = hosted_showbase' in a and 'real_showbase.__init__' not in a.lower())
check('scoped scene','holoutopia-native-scene' in a and 'self.render = context.scene_root' in a)
check('window mutation blocked','class _WindowProxy' in a and 'requestProperties' in a)
check('host camera alias used','self.camera = getattr(host, "camera", None)' in a and 'self.camLens = getattr(host, "camLens", None)' in a)
check('source tasks captured','class _TaskCaptureProxy' in a and '_run_captured_tasks' in a)
check('source events captured','self.accept = context.capture_accept' in a)
check('global taskMgr isolated','TaskManagerGlobal' in a and 'task_global.taskMgr = self._context.task_proxy' in a)
check('global base isolated','showbase_global.base = self._context.base_proxy' in a)
check('global messenger isolated','messenger_global.messenger = self._context.messenger_proxy' in a and 'direct_object_module.messenger = self._context.messenger_proxy' in a)
check('project path retained','sys.path.insert(0, root_text)' in a)
check('host settings borrowed','_sync_host_settings_to_delegate' in a and all(x in a for x in ('mouse_sensitivity','hud_visible','fov','master_volume','launch_width','launch_height')))
check('source settings restored','_restore_source_settings' in a and 'hosted_safe_save_config' in a)
check('host clear color restored','_snapshot_host_presentation' in a and '_restore_host_presentation' in a and 'getClearColor' in a)
check('gamepad attach does not mutate host','self.attachInputDevice = lambda' in a and 'self.detachInputDevice = lambda' in a)
check('HoloUtopia player controls bridged',all(f'"{k}"' in a for k in ('h','e','q','t','f1','f12','wheel_up','wheel_down','mouse1','mouse3')))
check('HoloUtopia numbered controls bridged','if action.startswith("number_")' in a)
check('TAB and ESC withheld from source','"escape", "pause", "menu", "return", "return_to_core", "tab"' in a and m.get('return_controls')==['TAB'])
check('no experimental host HUD requested',m.get('panel_supported') is False)
check('scene and UI cleanup','_collect_new_ui' in a and 'self._scene_root.clearFog()' in a and 'node.removeNode()' in a)
check('no source main/assets shipped',not (ROOT/'main.py').exists() and not (ROOT/'assets').exists())
if HV:
    hvmain=text(HV/'main.py'); persisted='\n'.join(text(p) for p in [HV/'main.py',HV/'holoverse/dimensions/links.py',HV/'holoverse/dimensions/registry.py'] if p.exists())
    check('host persistent link archive remains','dimension_archive.json' in persisted and 'LOCALAPPDATA' in persisted)
    check('host isolated dimension camera remains','def _begin_native_camera_isolation' in hvmain and 'native-dimension-camera' in hvmain)
    check('host freeze enforcement remains','def _enforce_native_host_freeze' in hvmain and 'self._enforce_native_host_freeze()' in hvmain)
    check('host TAB universal return','self.return_from_native_mode(reason="tab_return_home")' in hvmain)
    check('host ESC shared menu','def start_escape_hold' in hvmain)
    check('host no experimental dimension HUD','native_mode_status_root = self.aspect2d' not in hvmain and 'experimental_mode_status' not in hvmain)
    for k in ('"h"','"e"','"q"','"t"','"f1"','"f12"','"wheel_up"','"wheel_down"'):
        check(f'host forwards {k.strip(chr(34))}',k in hvmain)
fail=[]; count=0
for root in [ROOT]+([HV] if HV else []):
    for p in root.rglob('*.py'):
        if '__pycache__' in p.parts: continue
        count+=1
        try: ast.parse(text(p),filename=str(p))
        except Exception as e: fail.append(f'{p}: {e}')
check('all Python AST parse',not fail,f'{count} files'+(f'; {fail[:2]}' if fail else ''))
res=[]
for root in [ROOT]+([HV] if HV else []):
    for p in root.rglob('*'):
        if p.is_file() and (p.suffix=='.pyc' or '__pycache__' in p.parts): res.append(str(p))
check('no cache/pyc residue',not res,str(res[:4]))
passed=sum(ok for _,ok,_ in checks); print(f'RESULT {passed}/{len(checks)} PASS')
if passed!=len(checks): raise SystemExit(1)
