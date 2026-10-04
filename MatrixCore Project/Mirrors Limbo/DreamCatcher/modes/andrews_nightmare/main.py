from __future__ import annotations

import argparse
from pathlib import Path
import sys
import traceback

from panda3d.core import loadPrcFileData


def _mount_limbo_common() -> Path:
    """Andrew's Nightmare lives inside Mirror's Limbo; mount Limbo's shared gx_common package."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "gx_common" / "__init__.py").is_file():
            if str(parent) not in sys.path:
                sys.path.append(str(parent))
            return parent
    raise SystemExit("Andrew's Nightmare must stay inside the Mirror's Limbo folder (gx_common not found).")


_mount_limbo_common()


def parse_args():
    p = argparse.ArgumentParser(description="Andrew's Nightmare — DreamCatcher Mode")
    p.add_argument("--windowed", action="store_true", help="start in a 1280x720 decorated window")
    p.add_argument("--offscreen", action="store_true", help="use an offscreen Panda3D window")
    p.add_argument("--smoke-test", action="store_true", help="launch briefly and exit")
    p.add_argument("--self-test", action="store_true", help="run deterministic gameplay checks")
    p.add_argument("--qa-shot", metavar="PNG", help="capture a deterministic runtime screenshot then exit")
    p.add_argument("--qa-windowed", action="store_true", help="run QA screenshot through a real window instead of offscreen")
    p.add_argument(
        "--qa-scene",
        default="spawn",
        choices=["spawn", "junction", "lattice", "analog", "buffer", "stable", "archive", "feedback", "dead", "stabilized", "interaction", "relay-link", "archive-stable", "feedback-stable", "route-complete", "dreamer", "dreamer-close", "sleeper-side", "vision-blur", "vision-clear", "dreamer-recovered", "release-mosh", "released", "mosh", "cycle-a", "cycle-b", "false-hall", "false-hall-near", "dark-room", "glasses", "glasses-on", "lightless-room", "lightless-deep", "echo-room", "echo-near", "witness-alcove", "witness-near", "return-room", "return-near", "return-memory-a", "return-memory-b", "false-sleeper", "gleebs-trace", "memory-seam", "null-layer", "null-exit", "instance-collapse", "first-target", "false-sleeper-weakened", "resonance-charge", "resonance-read", "resonance-target-normal", "resonance-target-read", "false-sleeper-resonance", "sleeper-sink", "sleeper-ceiling", "sleeper-under"],
    )
    p.add_argument("--dream-seed", type=int, default=None, help="deterministic dream-cycle variation seed")
    p.add_argument("--no-audio", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    if args.offscreen:
        loadPrcFileData("offscreen", "load-display p3headlessgl")
    if ((args.qa_shot and not args.qa_windowed) or args.self_test or args.offscreen):
        loadPrcFileData("qa", "window-type offscreen\nwin-size 1920 1080\naudio-library-name null")
    elif args.qa_shot and args.qa_windowed:
        loadPrcFileData("qa-windowed", "win-size 1920 1080\naudio-library-name null")
    else:
        loadPrcFileData("runtime", "sync-video true\nframebuffer-multisample 1\nmultisamples 4\n")
    if args.no_audio:
        loadPrcFileData("noaudio", "audio-library-name null")
    from game.app import AndrewsNightmareApp
    root = Path(__file__).resolve().parent
    app = AndrewsNightmareApp(args, root)
    app.run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        from game.settings import user_data_dir
        report = traceback.format_exc()
        try:
            (user_data_dir() / "crash_latest.txt").write_text(report, encoding="utf-8")
        except OSError:
            pass
        print(report, file=sys.stderr)
        raise SystemExit(1)
