from __future__ import annotations

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import loadPrcFileData

loadPrcFileData("", "window-title The Archivist // Planetary Story Systems Pass 07")
loadPrcFileData("", "win-size 1280 720")
loadPrcFileData("", "sync-video true")
loadPrcFileData("", "framebuffer-multisample 1")
loadPrcFileData("", "multisamples 4")
loadPrcFileData("", "textures-power-2 none")

from archive3d.mode import ArchivistMode


class TheArchivistApp(ShowBase):
    def __init__(self):
        super().__init__()
        self.disableMouse()
        self.is_holoverse_host = False
        self.mode = ArchivistMode(self, entry_path=__file__)
        self.mode.enter()
        self.taskMgr.add(self._archive_frame, "archivist-standalone-frame")
        self.accept("f11", self._toggle_fullscreen)
        self.accept("q", self.userExit)

    def _archive_frame(self, task):
        self.mode.update(min(0.05, globalClock.getDt()))
        return Task.cont

    def _toggle_fullscreen(self):
        from panda3d.core import WindowProperties
        props = WindowProperties()
        current = bool(self.win.getProperties().getFullscreen())
        props.setFullscreen(not current)
        if current:
            props.setSize(1280,720)
        self.win.requestProperties(props)

    def userExit(self):
        try: self.mode.destroy()
        except Exception: pass
        super().userExit()


if __name__ == "__main__":
    TheArchivistApp().run()
