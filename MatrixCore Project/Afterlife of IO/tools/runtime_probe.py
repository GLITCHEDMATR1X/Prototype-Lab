from __future__ import annotations

"""Parent-process compatibility probe for the current Afterlife of IO build.

Every risky pygame/SDL operation is isolated in a child process.  A native SDL
crash therefore leaves this parent alive long enough to report the exact stage
and Windows status code.
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from build_info import DISPLAY_TITLE, PASS_NUMBER
STAGE_SCRIPT = Path(__file__).with_name("runtime_probe_stage.py")

CORE_STAGES = [
    "python",
    "pygame_import",
    "pygame_init",
    "display_plain",
    "surface_alpha_transform",
    "png_load_convert_scale",
    "walk_mask",
]
OPTIONAL_STAGES = ["mixer"]
GAME_STAGES = ["game_import", "game_smoke_safe", "game_smoke_normal"]

WINDOWS_STATUS = {
    0xC0000005: "ACCESS_VIOLATION",
    0xC000001D: "ILLEGAL_INSTRUCTION",
    0xC0000094: "INTEGER_DIVIDE_BY_ZERO",
    0xC00000FD: "STACK_OVERFLOW",
    0xC0000374: "HEAP_CORRUPTION",
    0xC0000409: "STACK_BUFFER_OVERRUN_OR_FAST_FAIL",
}


def report_dir() -> Path:
    candidates: list[Path] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "GLITCHED MATRIX" / "Afterlife of IO")
    candidates.extend([ROOT / "saves", Path(tempfile.gettempdir()) / "GLITCHED_MATRIX" / "Afterlife of IO"])
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test = path / ".probe_write_test"
            test.write_text("ok", encoding="ascii")
            test.unlink(missing_ok=True)
            return path
        except Exception:
            pass
    return ROOT


def decode_returncode(code: int) -> str | None:
    if code == 0:
        return None
    unsigned = code & 0xFFFFFFFF
    if unsigned in WINDOWS_STATUS:
        return f"0x{unsigned:08X} {WINDOWS_STATUS[unsigned]}"
    if unsigned >= 0x80000000:
        return f"0x{unsigned:08X} Windows/native process failure"
    return None


def parse_last_json(text: str) -> dict | None:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                return value
        except Exception:
            continue
    return None


def run_stage(stage: str, timeout: int) -> dict:
    cmd = [sys.executable, "-X", "faulthandler", str(STAGE_SCRIPT), stage]
    env = os.environ.copy()
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    env["PYTHONFAULTHANDLER"] = "1"
    started = datetime.now().isoformat(timespec="seconds")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        output = proc.stdout or ""
        payload = parse_last_json(output)
        status = "PASS" if proc.returncode == 0 else "FAIL"
        if payload and payload.get("status") == "SOFT_FAIL":
            status = "SOFT_FAIL"
        return {
            "stage": stage,
            "status": status,
            "return_code": proc.returncode,
            "native_status": decode_returncode(proc.returncode),
            "started": started,
            "payload": payload,
            "output": output[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stage": stage,
            "status": "TIMEOUT",
            "return_code": None,
            "native_status": None,
            "started": started,
            "payload": None,
            "output": ((exc.stdout or "") + (exc.stderr or ""))[-12000:] if isinstance(exc.stdout, str) else "",
        }


def compatibility_advisories(results: list[dict]) -> list[str]:
    notes: list[str] = []
    py = next((r.get("payload") for r in results if r["stage"] == "python" and r.get("payload")), {}) or {}
    pg = next((r.get("payload") for r in results if r["stage"] == "pygame_import" and r.get("payload")), {}) or {}
    version_info = py.get("version_info") or []
    pygame_version = str(pg.get("pygame_version", ""))
    sdl = pg.get("sdl_linked") or []
    if platform.system() == "Windows" and version_info[:2] >= [3, 14]:
        notes.append(
            "Python 3.14 detected. pygame-ce officially supports it, but a 2026 Windows 11 report describes a very similar blank-window/direct-exit failure with Python 3.14.3 + pygame-ce 2.5.7 + SDL 2.32.10. Prefer the project Python 3.12/3.11 runtime when available while diagnosing."
        )
    if pygame_version.startswith("2.5.7") and sdl[:3] == [2, 32, 10] and platform.system() == "Windows":
        notes.append("pygame-ce 2.5.7 with SDL 2.32.10 detected on Windows; record this exact stack if a native display stage fails.")
    return notes


def main() -> int:
    out_dir = report_dir()
    txt_path = out_dir / "runtime_probe_report.txt"
    json_path = out_dir / "runtime_probe_report.json"
    results: list[dict] = []

    print(f"{DISPLAY_TITLE} — Runtime + Game Startup Probe", flush=True)
    print(f"Interpreter: {sys.executable}", flush=True)
    print(f"Reports: {txt_path}", flush=True)
    print("Each risky SDL operation runs in a separate child process.\n", flush=True)

    core_failed = False
    for stage in CORE_STAGES:
        result = run_stage(stage, timeout=30)
        results.append(result)
        suffix = f" [{result['native_status']}]" if result.get("native_status") else ""
        print(f"{stage:28} {result['status']}{suffix}", flush=True)
        if result["status"] not in ("PASS", "SOFT_FAIL"):
            core_failed = True
            print("Core runtime stage failed. Later graphics/game stages are intentionally skipped to avoid repeated native crashes.", flush=True)
            break

    if not core_failed:
        for stage in OPTIONAL_STAGES:
            result = run_stage(stage, timeout=20)
            results.append(result)
            suffix = f" [{result['native_status']}]" if result.get("native_status") else ""
            print(f"{stage:28} {result['status']}{suffix}", flush=True)

        for stage in GAME_STAGES:
            result = run_stage(stage, timeout=90)
            results.append(result)
            suffix = f" [{result['native_status']}]" if result.get("native_status") else ""
            print(f"{stage:28} {result['status']}{suffix}", flush=True)
            if result["status"] not in ("PASS", "SOFT_FAIL"):
                if result.get("output"):
                    print("\n--- failing child output ---", flush=True)
                    for line in result["output"].splitlines()[-30:]:
                        print(line, flush=True)
                    print("--- end failing child output ---\n", flush=True)
                break

    advisories = compatibility_advisories(results)
    overall = "PASS"
    blocking = [r for r in results if r["stage"] != "mixer" and r["status"] != "PASS"]
    if blocking:
        overall = "FAIL"
    elif any(r["status"] == "SOFT_FAIL" for r in results):
        overall = "PASS_WITH_OPTIONAL_AUDIO_WARNING"

    report = {
        "schema": "afterlife.runtime_probe.v1",
        "pass": PASS_NUMBER,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "interpreter": sys.executable,
        "results": results,
        "advisories": advisories,
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        f"{DISPLAY_TITLE} — Runtime + Game Startup Probe",
        f"Generated: {report['generated']}",
        f"Overall: {overall}",
        f"Interpreter: {sys.executable}",
        "",
    ]
    for r in results:
        native = f" | {r['native_status']}" if r.get("native_status") else ""
        lines.append(f"{r['stage']}: {r['status']} | rc={r['return_code']}{native}")
        if r.get("payload"):
            lines.append("  " + json.dumps(r["payload"], sort_keys=True))
        if r.get("output") and r["status"] not in ("PASS", "SOFT_FAIL"):
            lines.append("  CHILD OUTPUT:")
            lines.extend("    " + line for line in r["output"].splitlines()[-40:])
    if advisories:
        lines += ["", "ADVISORIES:"] + [f"- {note}" for note in advisories]
    lines += [
        "",
        "Interpretation:",
        "- display_plain failure = Python/pygame/SDL/display stack, before game rendering.",
        "- surface/image/mask failure = pygame graphics operation used by the authored world.",
        "- game_import failure = Afterlife source/import boundary.",
        "- safe smoke failure = core world/startup path even with optional presentation disabled.",
        "- normal smoke failure after safe smoke PASS = optional FX/audio presentation path.",
    ]
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nOVERALL: {overall}", flush=True)
    if advisories:
        print("\nCompatibility advisory:", flush=True)
        for note in advisories:
            print("- " + note, flush=True)
    print(f"\nText report: {txt_path}", flush=True)
    print(f"JSON report: {json_path}", flush=True)
    return 0 if overall.startswith("PASS") else 3


if __name__ == "__main__":
    raise SystemExit(main())
