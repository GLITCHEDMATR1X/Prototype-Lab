"""Verify the HoloVerse link (holoverse_link.py + holoverse/ responder) without opening a window.

    python tools/verify_holoverse_link.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import holoverse_link as hl  # noqa: E402

checks: list[tuple[str, bool]] = []


def ck(name: str, cond) -> None:
    checks.append((name, bool(cond)))


responder = json.loads((ROOT / "holoverse" / "holoverse_dimension.json").read_text(encoding="utf-8"))
identity = json.loads((ROOT / "holoverse" / "identity.json").read_text(encoding="utf-8"))
ck("responder protocol", responder.get("protocol") == "holoverse_responder_v1")
ck("responder is linked (own window)", responder.get("compatibility") == "linked" and not responder.get("native_adapter"))
ck("responder entry is main.py", responder.get("entry") == "main.py" and (ROOT / "main.py").is_file())
ck("responder preview exists", (ROOT / str(responder.get("preview"))).is_file())
ck("fixed identity", len(str(identity.get("dimension_id", ""))) == 36)

for key in ("HOLOVERSE_LINK_MODE", "HOLOVERSE_RETURN_SIGNAL_PATH"):
    os.environ.pop(key, None)
ck("standalone: not hosted", not hl.hosted())
ck("standalone: QUIT stays QUIT", hl.quit_label("QUIT") == "QUIT" and hl.quit_label("QUIT TO DESKTOP") == "QUIT TO DESKTOP")
ck("standalone: nothing is written", hl.report_to_holoverse(3, False) is False)

signal_file = Path(tempfile.mkdtemp(prefix="afterlife_hv_")) / "external_return_signal.json"
os.environ["HOLOVERSE_LINK_MODE"] = "compatibility_external"
os.environ["HOLOVERSE_RETURN_SIGNAL_PATH"] = str(signal_file)
ck("hosted: detected", hl.hosted())
ck("hosted: RETURN TO HOLOVERSE", hl.quit_label("QUIT") == "RETURN TO HOLOVERSE")
hl.note_progress(2)
ck("hosted: result written", hl.report_to_holoverse(1, False) and signal_file.is_file())
res = json.loads(signal_file.read_text(encoding="utf-8")).get("result", {})
ck("result: session progress counts", res.get("fragments_recovered") == "2" and res.get("fragments_required") == "7")
ck("result: recovering signal", res.get("signal") == hl.SIGNAL_RECOVERING and res.get("completed") is False)
ck("result: no return request (HoloVerse just resumes)", "request" not in json.loads(signal_file.read_text()))
hl.report_to_holoverse(7, True)
res = json.loads(signal_file.read_text(encoding="utf-8")).get("result", {})
ck("result: campaign complete", res.get("completed") is True and res.get("signal") == hl.SIGNAL_COMPLETE)

for name, ok in checks:
    print(("PASS " if ok else "FAIL ") + name)
failed = [c for c in checks if not c[1]]
print(f"FINAL {'PASS' if not failed else 'FAIL'} {len(checks) - len(failed)}/{len(checks)}")
sys.exit(1 if failed else 0)
