from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .data import resolve_simulation


def enter_simulation(host, book: dict, fallback_internal: Path | None = None) -> tuple[bool, str]:
    book_id = str(book.get("id") or "")
    title = str(book.get("title") or book_id or "Simulation")
    main_path, state = resolve_simulation(book_id)

    # Inside HoloVerse, same-window nested dimensions are the only accepted path.
    push = getattr(host, "push_nested_native_entry", None)
    if callable(push):
        target = main_path
        if target is None and fallback_internal is not None:
            target = fallback_internal
            title = "Archive Echo"
        if target is None:
            return False, state
        try:
            ok = bool(push(Path(target), label=title, source="the_archivist"))
            return ok, "ENTERED NESTED REALITY" if ok else "REALITY HAS NO NATIVE ADAPTER"
        except Exception as exc:
            return False, f"NESTED ENTRY FAILED // {exc.__class__.__name__}"

    # Standalone development may still hand off to a legacy simulation process
    # or the built-in Archive Echo proof.
    if main_path is None and fallback_internal is not None:
        main_path = Path(fallback_internal)
        state = "INTERNAL ARCHIVE ECHO"
    if main_path is None:
        return False, state
    try:
        result = subprocess.run([sys.executable, os.fspath(main_path)], cwd=os.fspath(main_path.parent), check=False)
    except Exception as exc:
        return False, f"SIMULATION LAUNCH FAILED // {exc.__class__.__name__}"
    return result.returncode == 0, "SIMULATION CLOSED // RETURNED TO ARCHIVE" if result.returncode == 0 else f"SIMULATION EXITED {result.returncode}"
