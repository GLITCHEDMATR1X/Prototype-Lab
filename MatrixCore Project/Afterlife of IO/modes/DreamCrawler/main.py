"""Dream Crawler standalone launcher.

The game itself lives in ``dreamcrawler_core.py`` so Entropy can host archive
ruin dives in its own window without importing a launcher that opens one.
"""
import sys

import dreamcrawler_core as core


def main() -> int:
    return core.run_standalone()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        report = core.crash_report(exc)
        print("Dream Crawler crashed. Report written to:", report)
        raise
