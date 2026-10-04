from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "verify_pass29_controller_first.py",
    "verify_pass28_state_aware_music.py",
    "verify_pass25_complete_expedition.py",
    "verify_pass25_home_cache.py",
    "verify_pass25_ship_tutorial.py",
    "verify_pass26_hazard_personality.py",
    "verify_pass27_surface_landmarks.py",
    "verify_settings_audio.py",
    "verify_pass29_code_audit.py",
]


def main() -> int:
    results = []
    for name in SCRIPTS:
        proc = subprocess.run([sys.executable, "-B", str(ROOT / "tools" / name)], cwd=ROOT, text=True, capture_output=True)
        results.append({"script": name, "returncode": proc.returncode, "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-6000:]})
        print(f"{'PASS' if proc.returncode == 0 else 'FAIL'}: {name}")
        if proc.returncode != 0:
            if proc.stdout:
                print(proc.stdout)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
    report = {
        "pass": 29,
        "title": "Controller-First Expedition full regression",
        "scripts": len(results),
        "passed": sum(r["returncode"] == 0 for r in results),
        "result": "PASS" if all(r["returncode"] == 0 for r in results) else "FAIL",
        "results": results,
    }
    (ROOT / "Entropy_Pass29_regression.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"FINAL_RESULT={report['result']} ({report['passed']}/{report['scripts']})")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
