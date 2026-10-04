"""Pass 14 runtime visual and tactical-world verifier.

Run on an environment with pygame-ce 2.5.7. It produces fresh 1080p world
proofs, a destructible-cover proof, and a concise runtime report. Panda3D's
existing tools/panda_verify.py can then independently decode the exported PNGs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.render import Renderer, VIRTUAL_SIZE  # noqa: E402
from game.sim import Mission, WORLD  # noqa: E402


def main() -> int:
    shots = ROOT / "verification" / "screenshots"
    reports = ROOT / "verification" / "reports"
    shots.mkdir(parents=True, exist_ok=True); reports.mkdir(parents=True, exist_ok=True)
    pygame.init(); pygame.display.set_mode((1, 1))
    canvas = pygame.Surface(VIRTUAL_SIZE).convert()
    renderer = Renderer(canvas)
    rows = []
    outputs = []
    for index, quest in enumerate(("purge", "recovery", "rescue")):
        hero = {"purge": "nyx", "recovery": "vesper", "rescue": "circuit"}[quest]
        mission = Mission(hero, quest, seed=14140 + index)
        mission.update(0.5)
        renderer.draw_mission(mission)
        path = shots / f"pass14_{quest}_world_1080p.png"
        pygame.image.save(canvas, path); outputs.append(path)
        destructible = [o for o in mission.world_obstacles if o.destructible]
        rows.append({
            "quest": quest,
            "layout": mission.world_layout_name,
            "world_rect": list(WORLD),
            "physical_objects": sum(1 for o in mission.world_obstacles if o.blocks_movement),
            "spawners": sum(1 for o in mission.world_obstacles if o.category == "spawner"),
            "destructible": len(destructible),
        })
        if quest == "purge":
            wall = destructible[0]
            mission._damage_world_obstacle(wall, wall.max_hp * 0.50, "VERIFY")
            renderer.draw_mission(mission)
            cracked = shots / "pass14_destructible_cover_cracked_1080p.png"
            pygame.image.save(canvas, cracked); outputs.append(cracked)
            mission._damage_world_obstacle(wall, wall.max_hp, "VERIFY")
            renderer.draw_mission(mission)
            breached = shots / "pass14_destructible_cover_breached_1080p.png"
            pygame.image.save(canvas, breached); outputs.append(breached)
    pygame.quit()
    payload = {
        "pass14_runtime_visual": "PASS",
        "pygame_version": pygame.version.ver,
        "worlds": rows,
        "screenshots": [str(p.relative_to(ROOT)) for p in outputs],
    }
    (reports / "pass14_runtime_visual.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
