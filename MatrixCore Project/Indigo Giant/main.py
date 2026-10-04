"""The Indigo Giant - start here.

The Prototype Lab cabinet and RUN_INDIGO_GIANT.bat both run this file. The game itself is the
indigo_giant package beside it (Pass 62: this file used to hold the whole game).

    python main.py                 the title screen, then your journey
    python main.py --new           a new journey (the old save is kept as a backup)
    python main.py --no-title      straight into the journey
    python main.py --fps           show the frame-rate meter (F3 toggles it)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:          # also when started with python -I, or from another folder
    sys.path.insert(0, str(ROOT))

from indigo_giant.app import main  # noqa: E402

if __name__ == '__main__':
    main()
