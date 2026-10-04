from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "data" / "alternate_voice_lines.json"
MAIN = ROOT / "main.py"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def choose(rules, event, **context):
    for rule in rules:
        if rule.get("event") != event:
            continue
        ok = True
        for key, expected in rule.get("when", {}).items():
            if key.endswith("_min"):
                ok = context.get(key[:-4], 0) >= expected
            elif key.endswith("_max"):
                ok = context.get(key[:-4], 0) <= expected
            else:
                ok = context.get(key) == expected
            if not ok:
                break
        if ok:
            return rule.get("line_id")
    return None


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    lines = {x["id"]: x for x in cfg.get("lines", [])}
    if len(lines) != 14:
        fail(f"expected 14 preserved voice slots, found {len(lines)}")
    for line_id, entry in lines.items():
        asset = ROOT / entry["audio"]
        if not asset.is_file():
            fail(f"missing placeholder for {line_id}: {asset}")

    auth = cfg.get("behavior_authority", {})
    rules = auth.get("rules", [])
    expected = {
        ("tv_shutdown", 1, 0, 0): "tv_disobedience_01",
        ("tv_shutdown", 1, 3, 1): "tv_disobedience_02",
        ("tv_shutdown", 2, 0, 0): "tv_disobedience_02",
        ("tv_focus", None, 2, 0): "tv_watch_01",
        ("post_reset", None, 3, 1): "memory_02",
        ("post_reset", None, 6, 2): "memory_01",
        ("floor1_unlocked", None, 0, 0): "downstairs_01",
    }
    for (event, cycle, prior, resets), line_id in expected.items():
        ctx = {"prior_shutdowns": prior, "reset_cycles": resets}
        if cycle is not None:
            ctx["cycle_index"] = cycle
        actual = choose(rules, event, **ctx)
        if actual != line_id:
            fail(f"{event} {ctx} -> {actual!r}, expected {line_id!r}")

    if choose(rules, "tv_focus", prior_shutdowns=0, reset_cycles=0) is not None:
        fail("fresh TV focus should not produce unsolicited Alternate chatter")

    src = MAIN.read_text(encoding="utf-8")
    required_integration = [
        '"tv_shutdown",',
        '"post_reset",',
        '"floor1_unlocked",',
        '"tv_focus",',
        'alternate_voice_rules_fired.clear()',
        'alternate-voice-audio-resume',
    ]
    for token in required_integration:
        if token not in src:
            fail(f"main.py integration token missing: {token}")

    print("PASS: 14/14 authored Alternate voice slots preserved")
    print(f"PASS: {len(rules)} deterministic behavior rules validated")
    print("PASS: fresh TV focus remains silent")
    print("PASS: first/repeated shutdown selection differs by observed history")
    print("PASS: reset-memory and floor-unlock triggers are wired")
    print("PASS: TV bed duck/resume path is wired for voice clarity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
