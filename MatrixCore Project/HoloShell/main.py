"""Linkable HoloShell entry point.

The complete game remains implemented in HoloShell.py.  HoloVerse links projects
through main.py, so this wrapper exposes the real HoloShellApp embedding API and
preserves ordinary standalone launch behavior.
"""
from HoloShell import HoloShellApp, CommandHubApp, main

__all__ = ["HoloShellApp", "CommandHubApp", "main"]

if __name__ == "__main__":
    main()
