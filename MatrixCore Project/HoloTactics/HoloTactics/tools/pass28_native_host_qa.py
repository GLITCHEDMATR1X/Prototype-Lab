from __future__ import annotations
import json, sys, types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from panda3d.core import loadPrcFileData, Vec4
loadPrcFileData('', 'window-type offscreen')
loadPrcFileData('', 'audio-library-name null')
loadPrcFileData('', 'win-size 1280 720')
loadPrcFileData('', 'sync-video 0')
from direct.showbase.ShowBase import ShowBase
from direct.showbase.MessengerGlobal import messenger
from direct.task import Task

class Cfg:
    launch_width=1280; launch_height=720
    launch_fullscreen=False; launch_borderless=False; launch_bordered_fullscreen=False
    launch_vsync=False; launch_fps_cap=60; launch_ui_scale=1.0; launch_render_scale=1.0
    launch_hud_visible=True; launch_subtitles_enabled=True
    launch_mouse_sensitivity=0.22; launch_invert_y=False; launch_controller_deadzone=0.12
    launch_brightness=1.0; launch_contrast=1.0; launch_gamma=1.0; launch_graphics_quality='medium'
    master_volume=0.8; music_volume=0.7; sfx_volume=0.6; ambience_volume=0.5

class HostAudio:
    def __init__(self): self.stopped=[]
    def stop_loop(self, name): self.stopped.append(name)

class Host(ShowBase):
    def __init__(self):
        super().__init__(windowType='offscreen')
        self.cfg=Cfg(); self.audio=HostAudio(); self.returns=[]; self.host_events=[]
        self.accept('escape', lambda: self.host_events.append('escape'))
        self.accept('tab', lambda: self.host_events.append('tab'))
    def return_from_native_mode(self, reason='unknown'):
        self.returns.append(reason)

host=Host()
host.setBackgroundColor(0.12,0.13,0.14,1)
host.camera.setPos(3,-7,4)
host.camLens.setFov(47)
host.camLens.setNearFar(0.25,333)
sentinel=host.render.attachNewNode('host_world_sentinel')
hud_sentinel=host.aspect2d.attachNewNode('host_hud_sentinel')

def host_task(task): return Task.cont
sentinel_task=host.taskMgr.add(host_task,'host_sentinel_task')

from holoverse_native_adapter import create_mode, ADAPTER_VERSION

checks=[]
def check(name, ok, detail=None):
    checks.append({'name':name,'ok':bool(ok),'detail':detail})

initial_windows=len(host.graphicsEngine.getWindows())
initial_parent=host.camera.getParent()
initial_transform=host.camera.getTransform()
initial_fov=tuple(host.camLens.getFov())
initial_nf=(host.camLens.getNear(),host.camLens.getFar())
initial_bg=tuple(host.getBackgroundColor())

mode=create_mode(host, mode={'id':'holotactics','manifest':{'id':'holotactics'}})
for cycle in range(1,4):
    mode.enter()
    delegate=mode.delegate
    check(f'cycle{cycle}:entered', mode.get_diagnostics().get('entered') is True)
    check(f'cycle{cycle}:same_window', len(host.graphicsEngine.getWindows())==initial_windows)
    check(f'cycle{cycle}:borrowed_camera', getattr(delegate,'camera',None)==host.camera)
    check(f'cycle{cycle}:borrowed_taskmgr', getattr(delegate,'taskMgr',None)==host.taskMgr)
    accepted=set(messenger.getAllAccepting(delegate))
    check(f'cycle{cycle}:no_direct_host_keys', not accepted, sorted(accepted))
    check(f'cycle{cycle}:escape_reserved', mode.on_host_action('escape') is False)
    check(f'cycle{cycle}:return_reserved', mode.on_host_action('return') is False)
    mode.on_host_action('enter')
    before_cursor=tuple(delegate.state.cursor)
    consumed=mode.on_host_action('d')
    after_cursor=tuple(delegate.state.cursor)
    check(f'cycle{cycle}:forwarded_gameplay_action', consumed and after_cursor!=before_cursor, {'before':before_cursor,'after':after_cursor})
    mode.update(1/60)
    host.graphicsEngine.renderFrame(); host.graphicsEngine.renderFrame()
    if cycle==1:
        shot=ROOT/'reports'/('pass28_native_hosted'+'.png')
        shot.parent.mkdir(exist_ok=True)
        check('hosted_screenshot', bool(host.win.saveScreenshot(str(shot))), str(shot))
    messenger.send('escape'); messenger.send('tab')
    check(f'cycle{cycle}:host_escape_received', host.host_events[-2:]==['escape','tab'], host.host_events[-2:])
    check(f'cycle{cycle}:delegate_not_paused', not getattr(delegate,'is_paused',False))
    mode.exit()
    check(f'cycle{cycle}:exited', mode.get_diagnostics().get('entered') is False)
    check(f'cycle{cycle}:host_task_survives', host.taskMgr.hasTaskNamed('host_sentinel_task'))
    check(f'cycle{cycle}:host_world_survives', not sentinel.isEmpty())
    check(f'cycle{cycle}:host_hud_survives', not hud_sentinel.isEmpty())
    check(f'cycle{cycle}:window_count_restored', len(host.graphicsEngine.getWindows())==initial_windows)
    check(f'cycle{cycle}:camera_parent_restored', host.camera.getParent()==initial_parent)
    check(f'cycle{cycle}:camera_transform_restored', host.camera.getTransform().compareTo(initial_transform)==0)
    check(f'cycle{cycle}:fov_restored', all(abs(a-b)<1e-5 for a,b in zip(tuple(host.camLens.getFov()),initial_fov)), {'initial':initial_fov,'after':tuple(host.camLens.getFov())})
    check(f'cycle{cycle}:near_far_restored', (host.camLens.getNear(),host.camLens.getFar())==initial_nf)
    check(f'cycle{cycle}:background_restored', all(abs(a-b)<1e-6 for a,b in zip(tuple(host.getBackgroundColor()),initial_bg)))
    leaks=[n for n in host.render.findAllMatches('**/holotactics_scene_root')]
    hleaks=[n for n in host.aspect2d.findAllMatches('**/holotactics_hud_root')]
    check(f'cycle{cycle}:scene_cleanup', len(leaks)==0, len(leaks))
    check(f'cycle{cycle}:hud_cleanup', len(hleaks)==0, len(hleaks))

check('host_generic_native_music_stopped', host.audio.stopped.count('native_dimension_music')>=3, host.audio.stopped)
check('host_generic_air_stopped', host.audio.stopped.count('native_dimension_air')>=3, host.audio.stopped)
check('adapter_version_updated', ADAPTER_VERSION=='28.0-native-input-authority', ADAPTER_VERSION)

payload={'pass':28,'adapter_version':ADAPTER_VERSION,'checks':checks,'passed':sum(x['ok'] for x in checks),'total':len(checks),'ok':all(x['ok'] for x in checks)}
(ROOT/'reports'/'pass28_native_host_proof.json').write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps(payload,indent=2))
host.destroy()
if not payload['ok']:
    raise SystemExit(1)
