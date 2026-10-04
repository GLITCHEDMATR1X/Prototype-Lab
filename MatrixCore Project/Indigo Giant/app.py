"""Old entry point, kept only so existing shortcuts still work.

The game now starts from main.py (Pass 43). This file just runs it; it can be deleted.
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name('main.py')), run_name='__main__')
