"""Pass 27 crash reporter and mission recovery verifier. No pygame import required."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from game.crash_reporter import CrashReporter

    checks: dict[str, bool] = {}
    temp_root = Path(tempfile.mkdtemp(prefix="hex_pass27_crash_verify_"))
    try:
        project = temp_root / "Project"
        writable = temp_root / "UserData"
        project.mkdir(parents=True)
        reporter = CrashReporter()
        reporter.configure(project, writable, build_label="Pass 27 Verification")
        reporter.set_state_provider(lambda: {
            "ui_state": "MISSION",
            "selected_quest": "purge",
            "selected_hero": "nyx",
            "mission": {"layout": "Broken Nave Labyrinth", "party_size": 3, "enemy_count": 8},
            "profile_name": "save_profile.json",
        })
        reporter.breadcrumb("mission_launch_requested", hero="nyx", quest="purge", sidekicks=["circuit", "vesper"])
        try:
            def inner():
                raise RuntimeError(f"synthetic mission failure under {Path.home() / 'secret'}")
            inner()
        except RuntimeError as exc:
            artifact = reporter.capture_exception(exc, phase="mission_launch", recoverable=True, extra={"recover_to": "LOADOUT_PREP"})
        assert artifact is not None
        json_path = Path(artifact.json_path)
        text_path = Path(artifact.text_path)
        bundle_path = Path(artifact.bundle_path)
        checks["json_written"] = json_path.exists()
        checks["text_written"] = text_path.exists()
        checks["zip_bundle_written"] = bundle_path.exists() and zipfile.is_zipfile(bundle_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        checks["schema_version"] = payload.get("schema_version") == 2
        checks["mission_phase_captured"] = payload.get("phase") == "mission_launch" and payload.get("recoverable") is True
        checks["exception_captured"] = payload.get("exception", {}).get("type") == "RuntimeError" and "synthetic mission failure" in payload.get("exception", {}).get("message", "")
        checks["mission_state_captured"] = payload.get("game_state", {}).get("mission", {}).get("party_size") == 3
        checks["breadcrumbs_captured"] = any(row.get("event") == "mission_launch_requested" for row in payload.get("breadcrumbs", []))
        checks["privacy_contract"] = payload.get("privacy", {}).get("automatic_upload") is False and payload.get("privacy", {}).get("save_contents_included") is False
        raw = json_path.read_text(encoding="utf-8") + text_path.read_text(encoding="utf-8")
        checks["home_path_redacted"] = str(Path.home()) not in raw and "<HOME>" in raw
        with zipfile.ZipFile(bundle_path) as zf:
            names = set(zf.namelist())
        checks["bundle_contains_human_and_json"] = json_path.name in names and text_path.name in names
        checks["latest_pointer_written"] = (writable / "crashes" / "LATEST_CRASH.txt").exists()
        checks["fault_handler_log_local"] = (writable / "crashes" / "fatal_fault.log").exists()
        reporter.mark_clean_exit()
        # Simulate a prior-session fatal/native traceback: the next launch must
        # preserve it as a standalone local bundle even though no Python
        # exception handler would have had a chance to run.
        fault_log = writable / "crashes" / "fatal_fault.log"
        fault_log.write_text(f"Fatal Python error under {Path.home() / 'private'}\n", encoding="utf-8")
        next_reporter = CrashReporter()
        next_reporter.configure(project, writable, build_label="Pass 27 Verification Restart")
        native_bundles = list((writable / "crashes").glob("HEX_CONTRACT_previous_native_fault_NATIVE-*.zip"))
        checks["previous_native_fault_recovered"] = len(native_bundles) == 1 and (writable / "crashes" / "LATEST_CRASH.txt").exists()
        native_text = next((writable / "crashes").glob("HEX_CONTRACT_previous_native_fault_NATIVE-*.txt"))
        checks["native_fault_path_redacted"] = str(Path.home()) not in native_text.read_text(encoding="utf-8")
        next_reporter.mark_clean_exit()

        app = (ROOT / "game/app.py").read_text(encoding="utf-8")
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        spec = (ROOT / "platform/windows/HEXContract.spec").read_text(encoding="utf-8")
        checks["mission_launch_guard"] = 'phase="mission_launch"' in app and "profile_before = copy.deepcopy(self.profile)" in app
        checks["sidekick_cost_rollback"] = "mission_launch_rollback_saved" in app and "self.profile = profile_before" in app
        checks["mission_update_guard"] = 'phase="mission_update"' in app
        checks["mission_frame_guard"] = 'phase="mission_frame"' in app
        checks["crash_recovery_ui"] = 'self.state = "CRASH_RECOVERY"' in app and "_draw_crash_recovery" in app
        checks["crash_ui_bypasses_renderer"] = "pygame.font.Font" in app and 'if self.state != "CRASH_RECOVERY":\n            self.renderer.draw_platform_prompt' in app
        checks["top_level_guard_before_app_import"] = main_source.find("bootstrap_crash_reporter") < main_source.find("from game.app import main as app_main")
        checks["native_message_fallback"] = "show_native_error" in main_source
        checks["windowed_build_keeps_reporter"] = "disable_windowed_traceback=False" in spec
        checks["no_auto_upload_code"] = all(token not in (ROOT / "game/crash_reporter.py").read_text(encoding="utf-8").lower() for token in ("requests.post", "urllib.request", "http.client", "socket.connect"))

        ok = all(checks.values())
        result = {
            "pass27_crash_reporter": "PASS" if ok else "FAIL",
            "checks": checks,
            "report_fields": ["build", "phase", "exception", "runtime", "game_state", "extra", "breadcrumbs", "privacy"],
            "automatic_upload": False,
            "max_retained_report_sets": 20,
            "native_pygame_tested_in_container": False,
            "container_limit": "pygame-ce and Panda3D are unavailable from the configured package mirror",
        }
        out = ROOT / "verification/reports/pass27_crash_reporter.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0 if ok else 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
