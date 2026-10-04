from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "dreamcatcher_bridge.py"
spec = importlib.util.spec_from_file_location("dreamcatcher_bridge_under_test", MODULE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

with tempfile.TemporaryDirectory(prefix="dreamcatcher_bridge_") as temp:
    os.environ[bridge.BRIDGE_ENV] = temp
    handoff = bridge.make_handoff(
        bridge.WORLD_DREAMCATCHER_ALTERNATE,
        bridge.WORLD_ANDREWS_NIGHTMARE,
        "dream_channel",
        return_world=bridge.WORLD_DREAMCATCHER_ALTERNATE,
        session_id="bridge-self-test",
        payload={"probe": True},
    )
    path = bridge.write_handoff(handoff)
    reread = bridge.read_handoff()
    assert reread == handoff
    assert path == Path(temp) / "handoff.json"
    assert not (Path(temp) / "handoff.json.tmp").exists()
    bridge.clear_handoff()
    assert bridge.read_handoff() is None
print("DREAMCATCHER_BRIDGE_SCHEMA_1: PASS")
