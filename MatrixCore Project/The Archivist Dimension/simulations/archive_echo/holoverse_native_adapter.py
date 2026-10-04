from __future__ import annotations
import math
from pathlib import Path
from typing import Any

from direct.gui.DirectGui import DirectLabel
from panda3d.core import AmbientLight, TextNode, Vec3, WindowProperties

# Import the shared procedural box helper from the parent project.
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from archive3d.geometry import make_box


class HoloVerseNativeMode:
    def __init__(self, host, *, mode=None, entry_path=None, label="Archive Echo"):
        self.host=host; self.mode=dict(mode or {}); self.label=str(label or "Archive Echo")
        self.root=None; self.player=None; self.prompt=None; self.elapsed=0.0; self.destroyed=False
        self._owned=set(); self._keys={}

    def enter(self):
        self.root=self.host.render.attachNewNode("archivist_nested_archive_echo")
        self.host.setBackgroundColor(0.002,0.004,0.010,1)
        make_box(self.root,"echo_floor",(30,60,0.25),(0,0,-0.2),(0.01,0.018,0.028,1))
        for i in range(24):
            x=((i%6)-2.5)*3.3; y=(i//6)*8.0-10.0; z=1.0+(i%4)*0.8
            make_box(self.root,"echo_record",(1.4,0.25,2.0),(x,y,z),(0.18+0.02*(i%3),0.32,0.52+0.02*(i%4),1))
        self.player=self.host.render.attachNewNode("archive_echo_player"); self.player.setPos(0,-18,0)
        self.host.camera.reparentTo(self.player); self.host.camera.setPos(0,-8,4); self.host.camera.lookAt(self.player,0,5,1)
        try: self.host.camLens.setFov(72); self.host.camLens.setNearFar(0.08,500)
        except Exception: pass
        amb=AmbientLight("echo_ambient"); amb.setColor((0.22,0.30,0.48,1)); self.root.setLight(self.root.attachNewNode(amb))
        self.prompt=DirectLabel(parent=self.host.aspect2d,text="ARCHIVE ECHO // THE EMPTY FIELD // TAB RETURN TO THE ARCHIVIST",pos=(0,0,-0.9),scale=0.038,
                                frameColor=(0,0,0,0),text_fg=(0.66,0.86,0.94,0.95),text_align=TextNode.ACenter)
        for k in ("w","a","s","d"):
            self.host.accept(k,self._set,[k,True]); self.host.accept(k+"-up",self._set,[k,False]); self._owned|={k,k+"-up"}

    def _set(self,k,v): self._keys[k]=v

    def update(self,dt):
        self.elapsed+=float(dt or 0); move=Vec3(0,0,0)
        if self._keys.get("w"): move.y+=1
        if self._keys.get("s"): move.y-=1
        if self._keys.get("a"): move.x-=1
        if self._keys.get("d"): move.x+=1
        if move.lengthSquared()>0:
            move.normalize(); self.player.setPos(self.player.getPos()+move*4.2*min(0.05,float(dt or 0)))
        self.host.camera.lookAt(self.player,0,5,1+math.sin(self.elapsed*.5)*.2)

    def get_holoverse_result(self)->dict[str,Any]:
        return {"dimension":"archivist_archive_echo","completed":True,"signal":"empty_field_echo_observed"}

    def exit(self): self.destroy()
    def destroy(self):
        if self.destroyed:return
        self.destroyed=True
        for e in list(self._owned):
            try:self.host.ignore(e)
            except Exception:pass
        if self.prompt:
            try:self.prompt.destroy()
            except Exception:pass
        try:self.host.camera.reparentTo(self.host.render)
        except Exception:pass
        if self.player:
            try:self.player.removeNode()
            except Exception:pass
        if self.root:
            try:self.root.removeNode()
            except Exception:pass


def create_mode(host_app, *, mode=None, entry_path=None, label="Archive Echo"):
    return HoloVerseNativeMode(host_app,mode=mode,entry_path=entry_path,label=label)

create_adapter=create_mode
create_native_adapter=create_mode
