from __future__ import annotations

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import loadPrcFileData

loadPrcFileData("", "window-title The Archivist // Archive Echo")
loadPrcFileData("", "win-size 1280 720")

from holoverse_native_adapter import HoloVerseNativeMode

class ArchiveEchoApp(ShowBase):
    def __init__(self):
        super().__init__()
        self.disableMouse()
        self.mode=HoloVerseNativeMode(self,label="Archive Echo")
        self.mode.enter()
        self.taskMgr.add(self._frame,"archive-echo-frame")
        self.accept("tab",self.userExit)
        self.accept("escape",self.userExit)
        self.accept("q",self.userExit)
    def _frame(self,task):
        self.mode.update(min(0.05,globalClock.getDt()))
        return Task.cont
    def userExit(self):
        try:self.mode.destroy()
        except Exception:pass
        super().userExit()

if __name__=="__main__":
    ArchiveEchoApp().run()
