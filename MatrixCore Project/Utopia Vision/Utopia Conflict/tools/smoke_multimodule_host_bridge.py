"""Dependency-free lifecycle proof for Utopia Conflict Pass41.

This intentionally models the failure Pass40 missed: project-local parent modules
import Panda's *global* base/taskMgr/messenger and perform a deferred import plus
relative file access after construction.  The adapter must keep those contained
for the entire native visit, not only during main.py import.
"""
from __future__ import annotations
import importlib.util, os, sys, tempfile, types
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
    class P: x=111; y=222
    def getOrigin(self): return self.P()
class Window:
    def __init__(self): self.requests=0
    def getProperties(self): return Props()
    def requestProperties(self,p): self.requests+=1
class Manager:
    def __init__(self): self.v=.75
    def getVolume(self): return self.v
    def setVolume(self,v): self.v=v
class RealTaskMgr: pass
class RealMessenger:
    def __init__(self): self.events=[]
    def send(self,event,args=None,**kwargs): self.events.append((event,args or []))
class Cfg:
    launch_width=1920; launch_height=1080; launch_fullscreen=False; launch_borderless=False
    launch_bordered_fullscreen=True; launch_vsync=True; launch_fps_cap=60; launch_ui_scale=1.0
    launch_render_scale=1.0; launch_hud_visible=True; launch_game_mouse_sensitivity=.16
    launch_invert_y=False; launch_controller_deadzone=.15; master_volume=.8; music_volume=.5; sfx_volume=.7; ambience_volume=.4
class Host:
    def __init__(self):
        self.cfg=Cfg(); self.render=Node('render'); self.camera=Node('dimension-camera'); self.cam=Node('cam'); self.camNode=object(); self.camLens=object()
        self.win=Window(); self.loader=object(); self.graphicsEngine=object(); self.pipe=object(); self.mouseWatcherNode=object(); self.aspect2d=Node('aspect2d'); self.render2d=Node('render2d'); self.pixel2d=Node('pixel2d')
        self.sfxManagerList=[Manager()]; self.musicManager=Manager(); self.taskMgr=RealTaskMgr(); self.returned=[]; self.audio=types.SimpleNamespace(stop_loop=lambda name:None)
    def return_from_native_mode(self,reason=''): self.returned.append(reason)

# Fake Panda / Direct package surface.
direct=types.ModuleType('direct'); direct.__path__=[]; sys.modules['direct']=direct
showpkg=types.ModuleType('direct.showbase'); showpkg.__path__=[]; sys.modules['direct.showbase']=showpkg
class ShowBase:
    def __init__(self): raise AssertionError('second ShowBase constructor called')
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

orig_base=sg.base; orig_sg_task=sg.taskMgr; orig_tg_task=tmg.taskMgr; orig_messenger=mg.messenger; orig_direct_messenger=dom.messenger; orig_showbase=showmod.ShowBase; orig_prc=core.loadPrcFileData

with tempfile.TemporaryDirectory() as td:
    project=Path(td)
    (project/'runtime_asset.txt').write_text('REAL_UTOPIA_ASSET',encoding='utf-8')
    (project/'deferred_helper.py').write_text('VALUE="deferred-ok"\n',encoding='utf-8')
    (project/'base_workbench.py').write_text('''
from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import base, render
from direct.task.TaskManagerGlobal import taskMgr
from direct.showbase.MessengerGlobal import messenger
class CharacterWorkbenchApp(ShowBase):
    def __init__(self):
        super().__init__()
        self.accept("i", self.buy_armor)
        messenger.accept("g", self, self.global_event)
        taskMgr.add(self.base_tick, "base_tick", sort=-5)
        self.win.requestProperties(object())
        self.armor=10; self.ticks=0; self.global_hits=0; self.deferred=''; self.asset=''
    def buy_armor(self): self.armor += 10
    def global_event(self): self.global_hits += 1
    def base_tick(self,task):
        import deferred_helper
        self.deferred=deferred_helper.VALUE
        self.asset=open("runtime_asset.txt",encoding="utf-8").read().strip()
        assert base is not None and render is not None
        self.ticks += 1
        return task.cont
''',encoding='utf-8')
    (project/'prev_main.py').write_text('''
from base_workbench import CharacterWorkbenchApp
class PlaytestCharacterWorkbenchApp(CharacterWorkbenchApp):
    def update_playtest(self,dt): pass
''',encoding='utf-8')
    # Deliberately use a thin main.py wrapper. Pass41 rejected this layout
    # because it demanded all authority markers literally inside main.py.
    (project/'runtime_game.py').write_text('''
import prev_main as pm
WEAPON_LIBRARY=[{"id":"rifle"}]
class CombatWorkbenchApp(pm.PlaytestCharacterWorkbenchApp):
    def __init__(self):
        super().__init__(); self.runtime_mode="battle_ground"; self.battle_wave=1
        self.accept("1", self.deploy); self.taskMgr.add(self.update, "update", sort=10)
    def enter_battle_mode(self,air_mode=False): pass
    def update_playtest(self,dt): pass
    def deploy(self): self.deployed=True
    def update(self,task): self.battle_wave += 1; return task.cont
''',encoding='utf-8')
    (project/'main.py').write_text('''
# Thin wrapper on purpose. The real app is not imported until standalone main().
def main():
    import runtime_game
    app = runtime_game.CombatWorkbenchApp(); app.run()
if __name__ == "__main__":
    main()
''',encoding='utf-8')

    stale=types.ModuleType('prev_main'); stale.__file__='/tmp/unrelated/prev_main.py'; sys.modules['prev_main']=stale
    spec=importlib.util.spec_from_file_location('uc_adapter',ROOT/'holoverse_native_adapter.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    host=Host(); mode={'id':'u','manifest':{'dimension_id':'utopia-conflict-test'}}
    a=mod.create_mode(host,mode=mode,entry_path=project/'main.py',label='Utopia Conflict')
    a.enter()
    assert a.delegate.__class__.__name__=='CombatWorkbenchApp'
    assert a._window_mutation_requests==1
    # Runtime globals stay isolated AFTER constructor, the failure Pass40 missed.
    assert showmod.ShowBase is not orig_showbase
    assert sg.base is a._context.base_proxy
    assert sg.taskMgr is a._context.task_proxy and tmg.taskMgr is a._context.task_proxy
    assert mg.messenger is a._context.messenger_proxy and dom.messenger is a._context.messenger_proxy
    assert str(project) in sys.path
    assert a.on_host_action('i') and a.delegate.armor==20
    assert a.on_host_action('g') and a.delegate.global_hits==1
    assert a.on_host_action('number_1') and a.delegate.deployed is True
    cwd_before=Path.cwd(); before=a.delegate.battle_wave; a.update(.016)
    assert Path.cwd()==cwd_before
    assert a.delegate.battle_wave==before+1 and a.delegate.ticks==1
    assert a.delegate.deferred=='deferred-ok' and a.delegate.asset=='REAL_UTOPIA_ASSET'
    assert host.win.requests==0
    assert sys.modules.get('prev_main') is not stale
    a.exit()
    assert sys.modules.get('prev_main') is stale
    assert showmod.ShowBase is orig_showbase and core.loadPrcFileData is orig_prc
    assert sg.base is orig_base and sg.taskMgr is orig_sg_task and tmg.taskMgr is orig_tg_task
    assert mg.messenger is orig_messenger and dom.messenger is orig_direct_messenger
    assert str(project) not in sys.path
    assert host.sfxManagerList[0].v==.75 and host.musicManager.v==.75
    print('PASS42 WRAPPER ENTRY + PERSISTENT RUNTIME CONTEXT SMOKE PASS')
    print('wrapper_entry=PASS runtime_class_discovery=PASS global_taskMgr=ISOLATED global_base=ISOLATED messenger=ISOLATED deferred_import=PASS relative_runtime_asset=PASS cleanup=PASS')
