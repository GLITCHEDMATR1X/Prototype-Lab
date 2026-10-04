from __future__ import annotations

from direct.gui.DirectGui import DirectFrame, DirectLabel, DirectButton
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode, TransparencyAttrib


class NightmareUI:
    def __init__(self, base):
        self.base = base
        self.pause_root = base.aspect2d.attachNewNode("pause-ui")
        self.pause_root.hide()
        self.frame = DirectFrame(
            parent=self.pause_root,
            frameColor=(0.018, 0.012, 0.026, 0.91),
            frameSize=(-0.60, 0.60, -0.48, 0.48),
            relief=DGG.FLAT,
        )
        DirectFrame(parent=self.frame, frameColor=(0.08, 0.72, 0.90, 0.68), frameSize=(-0.59, 0.59, 0.451, 0.466), relief=None)
        DirectLabel(parent=self.frame, text="ANDREW'S NIGHTMARE", text_fg=(0.88, 0.95, 1, 1), text_scale=0.073, pos=(0, 0, 0.31), frameColor=(0,0,0,0))
        DirectLabel(parent=self.frame, text="PAUSED", text_fg=(1.0, 0.20, 0.70, 1), text_scale=0.045, pos=(0, 0, 0.21), frameColor=(0,0,0,0))
        controls = (
            "ESC / ENTER   RESUME\n"
            "WASD          MOVE\n"
            "MOUSE         LOOK\n"
            "SHIFT         SPRINT\n"
            "SPACE         JUMP\n"
            "CTRL          CROUCH\n"
            "F11           BORDERLESS / WINDOWED\n"
            "[  ]          FOV\n"
            "-  =          MOUSE SENSITIVITY\n"
            + "Q             RETURN TO DREAMCATCHER"
        )
        DirectLabel(parent=self.frame, text=controls, text_align=TextNode.ALeft, text_fg=(0.74, 0.83, 0.88, 1), text_scale=0.033, pos=(-0.43, 0, 0.11), frameColor=(0,0,0,0))
        self.status = DirectLabel(parent=self.frame, text="", text_fg=(0.28, 0.86, 1.0, 1), text_scale=0.031, pos=(0, 0, -0.39), frameColor=(0,0,0,0))

        DirectButton(parent=self.frame, text="RETURN TO DREAMCATCHER", text_scale=0.030,
            pos=(0, 0, -0.31), frameColor=(0.035, 0.07, 0.085, 1),
            frameSize=(-0.34, 0.34, -0.042, 0.042), relief=DGG.FLAT,
            text_fg=(0.72, 0.94, 0.95, 1), command=base.return_to_dreamcatcher)

        DirectButton(parent=self.frame, text="QUIT", text_scale=.026,
            pos=(.47,0,-.39), frameSize=(-.065,.065,-.03,.03), relief=DGG.FLAT,
            frameColor=(.04,.045,.05,1), text_fg=(.68,.72,.74,1), command=base.userExit)

        # Minimal crosshair only; no persistent explanatory HUD.
        self.crosshair = DirectLabel(text="+", text_fg=(0.78, 0.92, 0.98, 0.52), text_scale=0.028, pos=(0, 0, -0.012), frameColor=(0,0,0,0))
        self.interaction = DirectLabel(
            text="", text_fg=(0.76, 0.94, 1.0, 0.95), text_scale=0.038,
            pos=(0, 0, -0.86), frameColor=(0.012, 0.018, 0.030, 0.76),
            frameSize=(-0.39, 0.39, -0.060, 0.060), relief=None,
        )
        self.interaction.hide()

    def set_paused(self, paused: bool):
        if paused:
            self.pause_root.show()
            self.crosshair.hide()
            self.interaction.hide()
        else:
            self.pause_root.hide()
            self.crosshair.show()

    def set_interaction(self, text: str | None):
        if text:
            self.interaction["text"] = text
            self.interaction.show()
        else:
            self.interaction.hide()

    def set_status(self, text: str):
        self.status["text"] = text
