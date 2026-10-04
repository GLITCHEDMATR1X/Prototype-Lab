"""Compatibility responder for HoloVerse linked-project discovery.

The schema-2 manifest points to ``adapter/holoverse_adapter.py``.  This root
responder preserves compatibility with HoloVerse builds that discover sibling
projects by the historical ``holoverse_native_adapter.py`` filename.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_IMPL = Path(__file__).resolve().parent / "adapter" / "holoverse_adapter.py"
_spec = importlib.util.spec_from_file_location("mirrors_limbo_holoverse_adapter_impl", _IMPL)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Unable to load Mirror's Limbo HoloVerse adapter: {_IMPL}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
HoloVerseNativeMode = _mod.HoloVerseNativeMode
create_mode = _mod.create_mode
create_native_mode = _mod.create_native_mode
create_native_adapter = _mod.create_native_adapter
create_adapter = _mod.create_adapter
