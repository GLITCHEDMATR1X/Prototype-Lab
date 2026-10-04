from panda3d.core import loadPrcFileData

loadPrcFileData('', 'window-title Zonez')
loadPrcFileData('', 'win-size 1600 900')
loadPrcFileData('', 'sync-video true')
loadPrcFileData('', 'show-frame-rate-meter false')
loadPrcFileData('', 'default-fov 75')
loadPrcFileData('', 'cursor-hidden true')
loadPrcFileData('', 'textures-power-2 none')

from sandbox_proto.app import SandboxApp

import json
from pathlib import Path

try:
    from holoverse_link import install_exit_report
except Exception:  # standalone copies without the bridge keep working
    def install_exit_report(provider): return None


_ZONEZ_DIR = Path(__file__).resolve().parent   # resolved now: __file__ is gone by exit time


def _holoverse_result() -> dict:
    """Zonez is a sandbox: report the visit plus whatever progress the save file holds."""
    progress = {}
    try:
        progress = json.loads((_ZONEZ_DIR / "zonez_progress.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"completed": False, "signal": "zonez_visit",
            "gleebs_response": "Back from the Zonez. Every rule in there bends a little differently.",
            "progress": progress if isinstance(progress, dict) else {}}


if __name__ == '__main__':
    install_exit_report(_holoverse_result)
    app = SandboxApp()
    app.run()
