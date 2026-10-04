"""Compatibility entry for HoloShell.

HoloVerse loads holoverse_native_adapter.py for same-window travel. Running this
file directly simply starts the real HoloShell main.py entry point.
"""
from __future__ import annotations
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().with_name("main.py")), run_name="__main__")
