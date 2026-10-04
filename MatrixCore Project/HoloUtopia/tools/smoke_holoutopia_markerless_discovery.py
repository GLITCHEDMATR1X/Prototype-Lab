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
    engine=project/'engine'; engine.mkdir()
    (engine/'__init__.py').write_text('',encoding='utf-8')
    for i in range(7):
        (project/f'utility_{i}.py').write_text(f'VALUE={i}\n',encoding='utf-8')
    (project/'main.py').write_text('def main():\n    from engine.launcher import boot\n    boot()\nif __name__==\"__main__\": main()\n',encoding='utf-8')
    (engine/'launcher.py').write_text('def boot():\n    from .runtime_core import CivicSimulation\n    app=CivicSimulation()\n    app.run()\n',encoding='utf-8')
    (engine/'runtime_core.py').write_text('from direct.showbase.ShowBase import ShowBase\nfrom direct.task.TaskManagerGlobal import taskMgr\nclass CivicSimulation(ShowBase):\n    def __init__(self):\n        super().__init__(); self.ticks=0; self.flag=False\n        self.accept(\"h\",self.toggle)\n        taskMgr.add(self.update,\"sim-update\")\n    def toggle(self): self.flag=not self.flag\n    def update(self,task): self.ticks+=1; return task.cont\n',encoding='utf-8')
    assert len(list(project.rglob('*.py')))==11
    spec=importlib.util.spec_from_file_location('hu_adapter2',ROOT/'holoverse_native_adapter.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    host=Host(); a=mod.create_mode(host,mode={'id':'hu','manifest':{'dimension_id':'holoutopia-markerless'}},entry_path=project/'main.py',label='HoloUtopia')
    a.enter()
    assert a.delegate.__class__.__name__=='CivicSimulation'
    assert not any(a._source_features.get(k) for k in ('command_hub_app','utopia_civic_ring','streamed_worlds','player_update','weapon_system','building_system'))
    assert a._source_features.get('discovery_mode')=='authority_structural_class'
    assert a._source_features.get('launch_attempts')==[]
    assert 'sim-update' in a._captured_tasks
    before=a.delegate.ticks; a.update(.016); assert a.delegate.ticks==before+1
    assert a.on_host_action('h') and a.delegate.flag is True
    a.exit()
    assert (sg.base,sg.taskMgr,tmg.taskMgr,mg.messenger,dom.messenger,showmod.ShowBase,core.loadPrcFileData)==orig
    print('HOLOUTOPIA PASS03 MARKERLESS AUTHORITY SMOKE PASS')
    print('files=11 markers=NONE wrapper_main=BYPASSED runtime=CivicSimulation authority_scoring=PASS same_window=PASS cleanup=PASS')
