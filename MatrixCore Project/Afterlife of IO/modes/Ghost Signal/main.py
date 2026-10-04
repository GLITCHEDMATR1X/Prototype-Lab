from __future__ import annotations

import argparse
import sys
from pathlib import Path

from game.version import BUILD_LABEL, PROJECT_NAME, VERSION


def parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", 1)
        size = (int(width), int(height))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT") from exc
    if size[0] < 960 or size[1] < 540:
        raise argparse.ArgumentTypeError("minimum supported size is 960x540")
    return size


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{PROJECT_NAME} — {BUILD_LABEL}",
        epilog=f"Version {VERSION}",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--no-audio", action="store_true", help="Disable mixer initialization.")
    parser.add_argument("--quick-test", action="store_true", help="Run deterministic baseline checks and exit.")
    parser.add_argument("--acceptance-playthrough", choices=("blank", "migrated"), help=argparse.SUPPRESS)
    parser.add_argument("--release-input-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--windows-manual-assist", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--manual-assist-auto-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--manual-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--manual-assist-shot", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--scenario",
        choices=(
            "title",
            "city_map",
            "city_after_depot",
            "district_takeover",
            "profile_city",
            "profile_relaunch",
            "memory_archive",
            "gleebs_memory",
            "settings",
            "accessibility_city",
            "audio_caption",
            "pause",
            "help",
            "stage_polish",
            "gleebs_reduced",
            "annex_exterior",
            "annex_operations",
            "annex_core",
            "annex_captured",
            "annex_trace_failure",
            "annex_noisy",
            "annex_rejected",
            "annex_gleebs_warning",
            "gleebs_ejection",
            "city_lockout",
            "depot_yard",
            "depot_repair",
            "depot_drone",
            "depot_docked",
            "depot_core",
            "depot_captured",
            "depot_gleebs",
            "transit_platform",
            "transit_service",
            "transit_core",
            "transit_uplink",
            "transit_captured",
            "transit_gleebs",
            "commercial_spine_city",
            "mall_atrium",
            "mall_ad_grid",
            "mall_identity",
            "mall_core",
            "mall_captured",
            "mall_gleebs",
            "media_city",
            "media_ingest",
            "media_alert_router",
            "media_studio",
            "media_core",
            "media_captured",
            "media_gleebs",
            "financial_unlocked",
            "financial_city",
            "financial_floor",
            "financial_credentials",
            "financial_audit",
            "financial_core",
            "financial_captured",
            "financial_gleebs",
            "clinic_unlocked",
            "clinic_city",
            "clinic_triage",
            "clinic_identity",
            "clinic_life_support",
            "clinic_archive",
            "clinic_captured",
            "clinic_gleebs",
            "commercial_takeover",
            "industrial_grid_city",
            "factory_intake",
            "factory_line",
            "factory_safety",
            "factory_core",
            "factory_captured",
            "factory_gleebs",
            "power_grid_city",
            "power_dispatch",
            "power_switchyard",
            "power_feeders",
            "power_core",
            "power_captured",
            "power_gleebs",
            "drone_grid_city",
            "drone_parts",
            "drone_calibration",
            "drone_identity",
            "drone_core",
            "drone_captured",
            "drone_gleebs",
            "waste_grid_city",
            "waste_receiving",
            "waste_sorting",
            "waste_leachate",
            "waste_core",
            "waste_captured",
            "waste_gleebs",
            "industrial_controlled_city",
            "industrial_takeover",
            "industrial_cliffhanger",
            "onboarding_city",
            "onboarding_stage",
            "onboarding_method",
            "continue_title",
        ),
        default="title",
    )
    parser.add_argument("--test-shot", type=Path, help="Write a deterministic Pygame screenshot and exit.")
    parser.add_argument("--frames", type=int, default=12, help="Frames to run for automated modes.")
    parser.add_argument("--windowed", action="store_true", help="Launch bordered windowed mode.")
    parser.add_argument("--fullscreen", action="store_true", help="Launch desktop fullscreen mode.")
    parser.add_argument("--window-size", type=parse_size, default=(1920, 1080), help="Window size, e.g. 1280x720.")
    parser.add_argument("--auto-confirm", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--crash-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.crash_test:
            raise RuntimeError("V1 RC3 CRASH-LOG SELF TEST")
        if args.acceptance_playthrough:
            from game.acceptance_playthrough import run_acceptance_playthrough
            return run_acceptance_playthrough(args.acceptance_playthrough)
        if args.release_input_test:
            from game.release_input_test import run_release_input_test
            return run_release_input_test()
        if args.windows_manual_assist:
            from game.windows_manual_assistant import run_windows_manual_assistant
            return run_windows_manual_assistant(args.manual_report, auto_test=args.manual_assist_auto_test, screenshot_path=args.manual_assist_shot)

        from game.app import AppConfig, GhostSignalApp

        config = AppConfig(
            no_audio=args.no_audio,
            quick_test=args.quick_test,
            scenario=args.scenario,
            test_shot=args.test_shot,
            max_frames=max(1, args.frames) if (args.quick_test or args.test_shot) else None,
            fullscreen=args.fullscreen and not args.windowed,
            window_size=args.window_size,
            auto_confirm=args.auto_confirm,
        )
        return GhostSignalApp(config).run()
    except Exception as exc:
        from game.crash_report import show_native_crash_message, write_crash_report

        path = write_crash_report(exc)
        print(f"{PROJECT_NAME} failed. Crash report: {path}", file=sys.stderr)
        show_native_crash_message(path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
