from __future__ import annotations

"""Standard-library-only current build identity for Afterlife of IO.

Keep this module free of pygame/SDL imports so launch diagnostics can read the
same authority before the game runtime starts.
"""

PASS_NUMBER = 147
PASS_NAME = "Mode Hub"
DISPLAY_TITLE = f"Afterlife of IO — Pass {PASS_NUMBER} {PASS_NAME}"
