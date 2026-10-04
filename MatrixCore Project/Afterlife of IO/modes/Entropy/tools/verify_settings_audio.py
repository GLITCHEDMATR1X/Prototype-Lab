from __future__ import annotations

import ast
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> int:
    core = (ROOT / "space_core.py").read_text(encoding="utf-8")
    ui = (ROOT / "standard_ui.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    runtime = (ROOT / "runtime_paths.py").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    for path in (ROOT / "space_core.py", ROOT / "standard_ui.py", ROOT / "audio_ambience.py", ROOT / "music_score.py", ROOT / "runtime_paths.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    require(True, "active settings/audio modules parse")

    require("PAUSE_KEY" in core and "K_BACKQUOTE" in core and "set_paused(not paused)" in core, "backtick owns gameplay pause toggle")
    require("ESC PAUSE" not in core and "ESC PAUSE" not in ui, "legacy ESC pause hints removed")
    require('inp.roll_left = keys[pygame.K_q]' in core, "Q flight roll preserved")
    require('if key == pygame.K_q:' in core and 'running = False' in core, "Q pause-menu exit preserved")
    require("draw_settings_menu" in core and "draw_settings_menu" in ui, "settings page wired into pause UI")
    require('DISPLAY_MODES = ("bordered", "native_1080p", "fullscreen")' in core, "three display modes available")
    require("BORDERED_SIZES = ((1280, 720), (1600, 900), (1920, 1080))" in core, "three bordered sizes available")
    for key in ("master_volume", "music_volume", "sfx_volume", "ambience_volume", "audio_muted"):
        require(key in runtime and key in core, f"persistent {key} setting")
    score = (ROOT / "music_score.py").read_text(encoding="utf-8")
    require("STATE_BASE_VOLUME" in score and "0.62" in score and "0.50" in score, "state-aware music trims available")
    require("self.master_volume * self.music_volume" in core, "music mix independent from SFX/ambience")
    require("self.engine_base_volume = 0.68" in core and "self.engine_base_volume = 0.82" in core, "engine mix raised")
    require("0.62" in (ROOT / "audio_ambience.py").read_text(encoding="utf-8"), "surface ambience mix raised")
    require("pause or resume" in readme and "backtick" in readme.lower(), "README documents backtick pause")
    require(int(manifest.get("pass", 0)) >= 18, "manifest identifies a settings-preserving pass")

    # Runtime settings can be imported and migrated without pygame.
    with tempfile.TemporaryDirectory(prefix="entropy-settings-") as temp:
        env = os.environ.copy()
        env["ENTROPY_USER_DATA"] = temp
        import subprocess, sys
        code = (
            "import json, runtime_paths as r; "
            "s=r.load_settings(); "
            "assert s['schema_version']==4; "
            "assert s['window_mode']=='fullscreen'; "
            "assert s['music_volume']>=0.8; "
            "r.save_settings(s); "
            "assert r.SETTINGS_PATH.exists(); print(r.SETTINGS_PATH)"
        )
        subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    require(True, "settings default/save contract")

    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
