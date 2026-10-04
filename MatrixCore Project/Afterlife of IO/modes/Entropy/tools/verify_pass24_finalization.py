from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> int:
    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    runtime = (ROOT / "runtime_paths.py").read_text(encoding="utf-8")
    ambience = (ROOT / "audio_ambience.py").read_text(encoding="utf-8")
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    controls = (ROOT / "CONTROLS.txt").read_text(encoding="utf-8")
    itch = (ROOT / "ITCH_PAGE_DESCRIPTION.txt").read_text(encoding="utf-8")
    support = (ROOT / "SUPPORT.txt").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    for name in manifest["active_modules"]:
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "all active release modules parse")

    require('APP_VERSION = "Release Candidate 1 — Finalization"' in core, "runtime identity is corrected to RC1")
    require('parser.add_argument("--version"' in core, "runtime exposes a launcher-friendly version flag")
    require("Best-effort developer scaffolding" in core and "except OSError" in core, "asset scaffolding cannot block read-only installs")
    require('actual_mode = "bordered"\n            actual_mode' not in core, "duplicate display assignment is removed")
    require(core.count("Legacy projectile renderer remains dormant") == 1, "dormant projectile renderer is documented once")
    require("ship.vel = surface_return_state.get('vel'" in core and core.count("ship.vel = surface_return_state.get('vel'") == 2, "duplicate surface-return velocity assignment is removed")

    require("def _select_user_root" in runtime, "runtime selects a writable per-user root")
    require("tempfile.gettempdir()" in runtime, "restricted profiles have an OS-temp fallback")
    require('PROJECT_ROOT / "save_state.json"' in runtime, "legacy save migration remains supported")
    require("read_only_safe" in ambience, "ambient assets are read-only-install safe")
    require("if not force and version_ok and all_present" in ambience, "shipped ambience is not rewritten every launch")
    require("except OSError as exc" in ambience, "ambient regeneration failure is non-fatal")

    require("pygame-ce>=2.5.7,<2.6" in (ROOT / "requirements.txt").read_text(encoding="utf-8"), "pygame-ce support is pinned to the 2.5 API line")
    require("Entropy requires pygame-ce 2.5.x" in main_source, "missing source dependency has a clear message")
    require("pygame-ce" in readme and "not Panda3D" in readme, "README identifies the actual engine")
    require("%LOCALAPPDATA%" in readme and "%LOCALAPPDATA%" in support, "player documentation locates writable data")
    require("`               Pause / resume" in controls, "backtick pause is documented")
    require("polished release-candidate prototype" in itch.lower(), "itch copy discloses prototype status")
    require("One-minute survival" in itch and "Twelve alien world families" in itch, "itch copy accurately presents the core loop")
    require("active space-combat" in itch, "itch copy does not falsely advertise combat progression")

    require(manifest.get("pass") == 24, "manifest identifies Pass 24")
    require(manifest.get("release_status") == "release_candidate_1", "manifest identifies RC1 status")
    require(manifest.get("runtime") == "pygame-ce", "manifest identifies pygame-ce runtime")
    require(manifest.get("launcher_policy", "").startswith("source package only"), "manifest leaves standalone launcher packaging to the user")
    hardening = manifest.get("release_hardening", {})
    require(hardening.get("read_only_install_safe") is True, "manifest locks read-only install safety")
    require(hardening.get("development_history_excluded_from_itch_package") is True, "manifest locks clean itch packaging")

    with tempfile.TemporaryDirectory() as td:
        blocker = Path(td) / "not_a_directory"
        blocker.write_text("block", encoding="utf-8")
        code = (
            "import os,sys; "
            f"sys.path.insert(0, {str(ROOT)!r}); "
            f"os.environ['ENTROPY_USER_DATA']={str(blocker)!r}; "
            "import runtime_paths; "
            "print(runtime_paths.USER_ROOT); "
            "assert runtime_paths.USER_ROOT != runtime_paths._platform_root(); "
            "assert runtime_paths.USER_ROOT.is_dir()"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        require(proc.returncode == 0, "writable data root falls back when the preferred path is blocked")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
