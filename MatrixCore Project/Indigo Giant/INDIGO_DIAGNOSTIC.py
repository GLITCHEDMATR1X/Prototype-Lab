from __future__ import annotations

import importlib
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "indigo_diagnostic.log"
APP = ROOT / "main.py"
GLB = ROOT / "assets" / "Universal Animation Library[Standard]" / "Unreal-Godot" / "UAL1_Standard.glb"
SHADERS = (ROOT / "shaders" / "sketch.vert", ROOT / "shaders" / "sketch.frag")


def write(message: str = "") -> None:
    print(message, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def check_file(path: Path, label: str) -> bool:
    ok = path.is_file()
    size = path.stat().st_size if ok else 0
    write(f"{label}: {'OK' if ok else 'MISSING'} | {path} | {size} bytes")
    return ok


def module_version(name: str) -> tuple[bool, str]:
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", None)
        if version is None and name == "panda3d":
            try:
                from panda3d.core import PandaSystem
                version = PandaSystem.getVersionString()
            except Exception:
                version = "unknown"
        return True, str(version or "unknown")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    write("INDIGO GIANT PASS 37 - STARTUP DIAGNOSTIC")
    write(f"TIME: {datetime.now().isoformat(timespec='seconds')}")
    write(f"OS: {platform.platform()}")
    write(f"PYTHON: {sys.executable}")
    write(f"PYTHON_VERSION: {sys.version.replace(os.linesep, ' ')}")
    write(f"PROJECT_ROOT: {ROOT}")
    write()

    files_ok = check_file(APP, "APP")
    files_ok &= check_file(GLB, "GIANT_GLB")
    for shader in SHADERS:
        files_ok &= check_file(shader, f"SHADER_{shader.name}")

    write()
    deps_ok = True
    for module_name in ("numpy", "panda3d", "direct.showbase.ShowBase"):
        ok, detail = module_version(module_name)
        write(f"IMPORT {module_name}: {'OK' if ok else 'FAIL'} | {detail}")
        deps_ok &= ok

    if not files_ok or not deps_ok:
        write()
        write("RESULT: PRE-LAUNCH CHECK FAILED")
        write("The game was not modified or launched. Send indigo_diagnostic.log back for repair.")
        return 2

    write()
    write("PRE-LAUNCH CHECK: PASS")
    write("Launching main.py now.")
    write("Close the game normally if it opens. Any console output or traceback will be appended below.")
    write("--- APP OUTPUT START ---")

    try:
        with LOG.open("a", encoding="utf-8") as log_handle:
            proc = subprocess.run(
                [sys.executable, str(APP)],
                cwd=str(ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        write("--- APP OUTPUT END ---")
        write(f"APP_EXIT_CODE: {proc.returncode}")
        if proc.returncode == 0:
            write("RESULT: APP EXITED CLEANLY")
            return 0
        write("RESULT: APP FAILED OR TERMINATED WITH AN ERROR CODE")
        write("Send indigo_diagnostic.log back for repair.")
        return proc.returncode or 1
    except Exception:
        with LOG.open("a", encoding="utf-8") as fh:
            traceback.print_exc(file=fh)
        write("RESULT: DIAGNOSTIC WRAPPER FAILED WHILE STARTING APP")
        write("Send indigo_diagnostic.log back for repair.")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
