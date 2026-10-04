from pathlib import Path

from game.crash_reporter import bootstrap_crash_reporter

BUILD_LABEL = "Pass 32 Finalization UX Audio Build Fixes"


def _run() -> int:
    project_root = Path(__file__).resolve().parent
    reporter = bootstrap_crash_reporter(project_root, build_label=BUILD_LABEL)
    try:
        from game.app import main as app_main
        code = int(app_main() or 0)
        reporter.mark_clean_exit()
        return code
    except (KeyboardInterrupt, SystemExit):
        reporter.mark_clean_exit()
        raise
    except BaseException as exc:
        artifact = reporter.capture_exception(exc, phase="fatal_main", recoverable=False)
        reporter.show_native_error(artifact)
        return 1


if __name__ == "__main__":
    raise SystemExit(_run())
