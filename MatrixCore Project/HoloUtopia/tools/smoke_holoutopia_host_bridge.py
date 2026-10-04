"""Dependency-free proof for HoloUtopia native HoloVerse integration."""
from __future__ import annotations
import importlib.util, json, sys, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Node:
    def __init__(self,name='node'): self.name=name; self.children=[]; self.empty=False
    def attachNewNode(self,obj): n=Node(str(obj)); self.children.append(n); return n
    def getChildren(self): return list(self.children)
    def node(self): return self
    def isEmpty(self): return self.empty
    def clearFog(self): pass
    def clearLight(self): pass
    def removeNode(self): self.empty=True
    def getPos(self,*a): return (0,0,0)
    def getHpr(self,*a): return (0,0,0)
class Props:
    class P: x=333; y=444
    def getOrigin(self): return self.P()
class Window:
    def __init__(self): self.requests=0; self.clear='HOST_CLEAR'
    def getProperties(self): return Props()
    def requestProperties(self,p): self.requests+=1
    def getClearColor(self): return self.clear
    def setClearColor(self,c): self.clear=c
class Lens:
    def __init__(self): self.fov=70
    def setFov(self,v): self.fov=float(v)
class Manager:
    def __init__(self): self.v=.75
    def getVolume(self): return self.v
    def setVolume(self,v): self.v=v
class RealTaskMgr: pass
class RealMessenger:
    def __init__(self): self.events=[]
    def send(self,event,args=None,**kwargs): self.events.append((event,args or []))
class HostCfg:
    launch_width=1920; launch_height=1080; launch_fullscreen=False; launch_borderless=False
    launch_bordered_fullscreen=True; launch_vsync=True; launch_fps_cap=60; launch_ui_scale=1.0
    launch_render_scale=1.0; launch_hud_visible=False; launch_game_mouse_sensitivity=.31
    launch_invert_y=False; launch_controller_deadzone=.17; master_volume=.61; music_volume=.42; sfx_volume=.73; ambience_volume=.55
    fov=88.0; graphics_quality='high'
class Host:
    def __init__(self):
        self.cfg=HostCfg(); self.render=Node('render'); self.camera=Node('dimension-camera'); self.cam=Node('cam'); self.camNode=object(); self.camLens=Lens()
        self.win=Window(); self.loader=object(); self.graphicsEngine=object(); self.pipe=object(); self.mouseWatcherNode=object(); self.aspect2d=Node('aspect2d'); self.render2d=Node('render2d'); self.pixel2d=Node('pixel2d')
        self.sfxManagerList=[Manager()]; self.musicManager=Manager(); self.taskMgr=RealTaskMgr(); self.returned=[]; self.audio=types.SimpleNamespace(stop_loop=lambda name:None); self.devices=types.SimpleNamespace(getDevices=lambda cls:[])
    def return_from_native_mode(self,reason=''): self.returned.append(reason)

# Fake Panda / Direct package surface.
direct=types.ModuleType('direct'); direct.__path__=[]; sys.modules['direct']=direct
showpkg=types.ModuleType('direct.showbase'); showpkg.__path__=[]; sys.modules['direct.showbase']=showpkg
class ShowBase:
    def __init__(self): raise AssertionError('second ShowBase constructor called')
    def setBackgroundColor(self,*args):
        val=args[0] if len(args)==1 else tuple(args)
        self.win.setClearColor(val)
showmod=types.ModuleType('direct.showbase.ShowBase'); showmod.ShowBase=ShowBase; sys.modules['direct.showbase.ShowBase']=showmod
real_task_mgr=RealTaskMgr(); real_messenger=RealMessenger()
sg=types.ModuleType('direct.showbase.ShowBaseGlobal'); sg.base=object(); sg.render=Node('global-render'); sg.camera=Node('global-camera'); sg.cam=Node('global-cam'); sg.taskMgr=real_task_mgr; sg.loader=object(); sg.messenger=real_messenger; sys.modules['direct.showbase.ShowBaseGlobal']=sg
mg=types.ModuleType('direct.showbase.MessengerGlobal'); mg.messenger=real_messenger; sys.modules['direct.showbase.MessengerGlobal']=mg
dom=types.ModuleType('direct.showbase.DirectObject'); dom.messenger=real_messenger; sys.modules['direct.showbase.DirectObject']=dom
taskpkg=types.ModuleType('direct.task'); taskpkg.__path__=[]
class Task: cont='cont'; done='done'; again='again'
taskpkg.Task=Task; sys.modules['direct.task']=taskpkg
tmg=types.ModuleType('direct.task.TaskManagerGlobal'); tmg.taskMgr=real_task_mgr; sys.modules['direct.task.TaskManagerGlobal']=tmg
panda=types.ModuleType('panda3d'); panda.__path__=[]; sys.modules['panda3d']=panda
core=types.ModuleType('panda3d.core'); core.loadPrcFileData=lambda *a,**k:None; sys.modules['panda3d.core']=core

orig=(sg.base,sg.taskMgr,tmg.taskMgr,mg.messenger,dom.messenger,showmod.ShowBase,core.loadPrcFileData)
with tempfile.TemporaryDirectory() as td:
    project=Path(td)
    (project/'runtime_asset.txt').write_text('HOLOUTOPIA_RUNTIME_ASSET',encoding='utf-8')
    (project/'deferred_world.py').write_text('VALUE="world-stream-ok"\n',encoding='utf-8')
    # Thin selected main.py, matching the wrapper-safe pattern.
    (project/'main.py').write_text('''\ndef main():\n    import observatory_runtime\n    app=observatory_runtime.CommandHubApp(); app.run()\nif __name__=="__main__": main()\n''',encoding='utf-8')
    (project/'observatory_runtime.py').write_text('''\nimport json\nfrom types import SimpleNamespace\nfrom direct.showbase.ShowBase import ShowBase\nfrom direct.showbase.ShowBaseGlobal import base, render\nfrom direct.task.TaskManagerGlobal import taskMgr\nfrom direct.showbase.MessengerGlobal import messenger\nWORLD_SPECS={0:{"name":"Holo-Utopia Civic Ring","kind":"utopia"},5:{"name":"Void Fleet Lens","kind":"space"},6:{"name":"Aqua Abyss Lens","kind":"underwater"}}\nclass Cfg:\n    mouse_sensitivity=.11; hud_visible=True; fov=82.; master_volume=.82; music_volume=.42; sfx_volume=.82; ambience_volume=.58\n    launch_width=1600; launch_height=900; launch_fullscreen=False; launch_borderless=False; launch_game_mouse_sensitivity=.22; launch_invert_y=False; launch_hud_visible=True; launch_graphics_quality="medium"; launch_controller_deadzone=.12\n    world_fill_mode="transparent"\ndef save_config(cfg):\n    open("source_saved.json","w",encoding="utf-8").write(json.dumps({k:getattr(cfg,k) for k in ("mouse_sensitivity","hud_visible","fov","master_volume","music_volume","sfx_volume","ambience_volume","launch_width","launch_height","world_fill_mode")},sort_keys=True))\nclass CommandHubApp(ShowBase):\n    def __init__(self):\n        super().__init__(); self.cfg=Cfg(); self.hud_visible=self.cfg.hud_visible; self.user_buildings={}; self.active_artifact_id=0; self.world_unlocked=True; self.internal_mode=SimpleNamespace(mode_key=""); self.ticks=0; self.deferred=""; self.asset=""\n        self.setBackgroundColor("UTOPIA_CLEAR")\n        self.win.requestProperties(object())\n        self.accept("h",self.toggle_hud); self.accept("e",self.interact); self.accept("q",self.secondary); self.accept("1",self.core_launch_campaign); self.accept("2",self.core_launch_fractured_boss); self.accept("5",self.toggle_infill); self.accept("6",self.cycle_world_fill_mode); self.accept("t",self.teleport); self.accept("f1",self.help); self.accept("f12",self.shot)\n        taskMgr.add(self.update_task,"update-task")\n    def setup_weapon_system(self): pass\n    def update_player(self,dt): pass\n    def update_world_chunks(self): pass\n    def rebuild_station(self): pass\n    def refresh_ui(self): pass\n    def activate_internal_mode(self,key): self.internal_mode.mode_key=key\n    def setup_input(self): pass\n    def toggle_hud(self): self.hud_visible=not self.hud_visible\n    def interact(self): self.interacted=True\n    def secondary(self): self.secondary_used=True\n    def core_launch_campaign(self): self.activate_internal_mode("campaign")\n    def core_launch_fractured_boss(self): self.activate_internal_mode("fractured_boss")\n    def toggle_infill(self): self.infill=True\n    def cycle_world_fill_mode(self): self.cfg.world_fill_mode="solid"; save_config(self.cfg)\n    def teleport(self): self.teleported=True\n    def help(self): self.helped=True\n    def shot(self): self.shot_taken=True\n    def current_world_spec(self): return WORLD_SPECS[0]\n    def update_task(self,task):\n        import deferred_world\n        self.deferred=deferred_world.VALUE; self.asset=open("runtime_asset.txt",encoding="utf-8").read().strip(); self.ticks+=1\n        assert base is not None and render is not None\n        return task.cont\n''',encoding='utf-8')
    spec=importlib.util.spec_from_file_location('hu_adapter',ROOT/'holoverse_native_adapter.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    host=Host(); a=mod.create_mode(host,mode={'id':'hu','manifest':{'dimension_id':'holoutopia-test'}},entry_path=project/'main.py',label='HoloUtopia')
    a.enter()
    assert a.delegate.__class__.__name__=='CommandHubApp'
    assert a._window_mutation_requests==1 and host.win.requests==0
    assert host.win.clear=='UTOPIA_CLEAR'
    assert showmod.ShowBase is not orig[5] and sg.taskMgr is a._context.task_proxy and tmg.taskMgr is a._context.task_proxy
    assert mg.messenger is a._context.messenger_proxy and dom.messenger is a._context.messenger_proxy
    assert abs(a.delegate.cfg.mouse_sensitivity-.31)<1e-9 and a.delegate.cfg.hud_visible is False and abs(a.delegate.cfg.fov-88)<1e-9
    assert abs(a.delegate.cfg.master_volume-.61)<1e-9 and a.delegate.cfg.launch_width==1920 and a.delegate.cfg.launch_height==1080
    assert a.on_host_action('number_1') and a.delegate.internal_mode.mode_key=='campaign'
    assert a.on_host_action('number_6') and a.delegate.cfg.world_fill_mode=='solid'
    saved=json.loads((project/'source_saved.json').read_text())
    # HoloVerse settings are transient; standalone source values remain on disk.
    assert abs(saved['mouse_sensitivity']-.11)<1e-9 and saved['hud_visible'] is True and saved['launch_width']==1600 and saved['world_fill_mode']=='solid'
    before=a.delegate.ticks; a.update(.016); assert a.delegate.ticks==before+1 and a.delegate.deferred=='world-stream-ok' and a.delegate.asset=='HOLOUTOPIA_RUNTIME_ASSET'
    result=a.get_holoverse_result(); assert result['world_name']=='Holo-Utopia Civic Ring' and result['world_kind']=='utopia'
    d=a.delegate; a.exit()
    assert host.win.clear=='HOST_CLEAR'
    assert abs(d.cfg.mouse_sensitivity-.11)<1e-9 and d.cfg.hud_visible is True and abs(d.cfg.fov-82)<1e-9
    assert (sg.base,sg.taskMgr,tmg.taskMgr,mg.messenger,dom.messenger,showmod.ShowBase,core.loadPrcFileData)==orig
    saved=json.loads((project/'source_saved.json').read_text()); assert saved['world_fill_mode']=='solid' and saved['launch_width']==1600
    assert host.sfxManagerList[0].v==.75 and host.musicManager.v==.75
    print('HOLOUTOPIA PASS01 NATIVE BRIDGE SMOKE PASS')
    print('runtime_discovery=PASS same_window=PASS config_borrow=PASS config_restore=PASS host_clear_restore=PASS task_global=ISOLATED messenger=ISOLATED deferred_import=PASS relative_asset=PASS cleanup=PASS')
