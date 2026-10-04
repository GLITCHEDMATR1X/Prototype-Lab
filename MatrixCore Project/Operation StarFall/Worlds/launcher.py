from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from display_config import inherited_display_args
from transport_link import normalize_game_id, target_script, transport_link_self_test, write_active_game, write_transport_state

ROOT = Path(__file__).resolve().parent


def launch(game: str, *, wait: bool = False, dry_run: bool = False) -> int:
    game_id = normalize_game_id(game)
    script = target_script(game_id, __file__)
    if not script.exists():
        print(f"LAUNCHER FAIL missing target: {script}", flush=True)
        return 2
    write_transport_state("launcher", game_id, __file__, reason="launcher")
    write_active_game(game_id, __file__)
    launch_args = [sys.executable, str(script)] + inherited_display_args(sys.argv)
    if game_id in {"enceladus", "mimas", "iapetus", "titan", "mars", "pluto", "europa", "triton"}:
        launch_args.append(f"--moon={game_id}")
    if dry_run:
        print(f"LAUNCHER_DRY_RUN PASS game={game_id} args={launch_args}", flush=True)
        return 0
    proc = subprocess.Popen(launch_args, cwd=str(script.parent))
    if wait:
        return int(proc.wait())
    print(f"LAUNCHER PASS started {game_id}: {script}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Operation StarFall linked mission launcher")
    parser.add_argument("--game", default="mimas", choices=["enceladus", "enceladus_ice", "mimas", "mimas_snowfield", "iapetus", "titan", "mars", "pluto", "europa", "triton", "starfall", "starfall_salvage"], help="Mission to launch.")
    parser.add_argument("--wait", action="store_true", help="Wait for the launched game process to exit.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and print the launch command without starting Panda3D.")
    parser.add_argument("--self-test", action="store_true", help="Check that all registered linked mission entry points exist.")
    # Display flags are accepted here so run_game.bat and Prototype Lab can pass
    # them through the launcher instead of argparse rejecting them before the game
    # starts.  display_config.inherited_display_args(sys.argv) decides which one
    # is forwarded to the target mission.
    for flag in ["--desktop-window", "--fullscreen", "--bordered-fullscreen", "--decorated-fullscreen", "--bordered-window", "--safe-window", "--large-window", "--windowed-fullscreen", "--full-windowed", "--borderless", "--windowed"]:
        parser.add_argument(flag, action="store_true")
    args = parser.parse_args()
    if args.self_test:
        info = transport_link_self_test(__file__)
        ok = bool(all(info.get(f"{world}_exists") for world in ("enceladus", "mimas", "iapetus", "titan", "mars", "pluto", "europa", "triton", "starfall")) and info.get("registry_entries_exist"))
        print(("LAUNCHER_SELF_TEST PASS " if ok else "LAUNCHER_SELF_TEST FAIL ") + str(info), flush=True)
        return 0 if ok else 1
    return launch(args.game, wait=args.wait, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
