"""Pure-Python geometry validator for Pass 14 tactical worlds.

It deliberately avoids pygame so clearance/path gates can run in constrained build
environments as well as in the shipped source tree.
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.world_data import (  # noqa: E402
    LAYOUTS, PREFABS, WORLD_RECT, MAX_ACTOR_RADIUS, MIN_CLEAR_GAP,
    SPAWN_CLEARANCE, EDGE_CLEARANCE, expand_object,
)


def rect_distance(a, b) -> float:
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ar, ab = ax + aw, ay + ah; br, bb = bx + bw, by + bh
    dx = max(bx - ar, ax - br, 0)
    dy = max(by - ab, ay - bb, 0)
    return math.hypot(dx, dy)


def point_rect_distance(point, rect) -> float:
    px, py = point; x, y, w, h = rect
    cx = min(max(px, x), x + w); cy = min(max(py, y), y + h)
    return math.hypot(px - cx, py - cy)


def inflated(rect, amount):
    x, y, w, h = rect
    return (x - amount, y - amount, w + amount * 2, h + amount * 2)


def contains_point(rect, point):
    x, y, w, h = rect; px, py = point
    return x <= px <= x + w and y <= py <= y + h


def walkable(point, parts, radius):
    wx, wy, ww, wh = WORLD_RECT
    px, py = point
    if not (wx + radius <= px <= wx + ww - radius and wy + radius <= py <= wy + wh - radius):
        return False
    return not any(contains_point(inflated(r, radius + 4), point) for r in parts)


def reachable(start, goals, parts, radius=MAX_ACTOR_RADIUS, cell=24):
    wx, wy, ww, wh = WORLD_RECT
    xs = list(range(wx + radius, wx + ww - radius + 1, cell))
    ys = list(range(wy + radius, wy + wh - radius + 1, cell))
    valid = {(x, y) for x in xs for y in ys if walkable((x, y), parts, radius)}
    if not valid:
        return set()
    s = min(valid, key=lambda p: math.dist(p, start))
    q = deque([s]); seen = {s}
    directions = ((cell,0),(-cell,0),(0,cell),(0,-cell),(cell,cell),(cell,-cell),(-cell,cell),(-cell,-cell))
    while q:
        x, y = q.popleft()
        for dx, dy in directions:
            n = (x + dx, y + dy)
            if n in valid and n not in seen:
                seen.add(n); q.append(n)
    reached = set()
    for name, pos in goals.items():
        nearest = min(valid, key=lambda p: math.dist(p, pos))
        if nearest in seen:
            reached.add(name)
    return reached


def validate_layout(key: str) -> dict:
    layout = LAYOUTS[key]
    expanded = [expand_object(obj) for obj in layout["objects"]]
    physical = [obj for obj in expanded if obj["movement"]]
    all_parts = [part for obj in physical for part in obj["parts"]]
    wx, wy, ww, wh = WORLD_RECT
    world_right, world_bottom = wx + ww, wy + wh
    issues = []

    for obj in physical:
        for part in obj["parts"]:
            x, y, w, h = part
            if not (x >= wx + EDGE_CLEARANCE and y >= wy + EDGE_CLEARANCE and x + w <= world_right - EDGE_CLEARANCE and y + h <= world_bottom - EDGE_CLEARANCE):
                issues.append(f"{obj['id']} violates edge clearance: {part}")

    pair_distances = []
    for i, a in enumerate(physical):
        for b in physical[i+1:]:
            d = rect_distance(a["bounds"], b["bounds"])
            pair_distances.append(d)
            if d < MIN_CLEAR_GAP:
                issues.append(f"{a['id']} / {b['id']} gap {d:.1f} < {MIN_CLEAR_GAP}")

    marker_checks = {}
    for name, pos in layout["markers"].items():
        if name.startswith(("boss", "spawn_gate")):
            required = 120
        elif name.startswith(("enemy_", "comp_", "civilian_")):
            required = 96
        else:
            required = 88
        nearest = min((point_rect_distance(pos, part) for part in all_parts), default=9999.0)
        marker_checks[name] = round(nearest, 2)
        if nearest < required:
            issues.append(f"marker {name} clearance {nearest:.1f} < {required}")

    # Live actors/objectives must not be authored on top of one another.
    live_markers = {name: pos for name, pos in layout["markers"].items() if name.startswith(("enemy_", "comp_", "boss", "civilian_")) or name == "artifact"}
    marker_pair_min = 9999.0
    live_items = list(live_markers.items())
    for i, (an, ap) in enumerate(live_items):
        for bn, bp in live_items[i+1:]:
            d = math.dist(ap, bp)
            marker_pair_min = min(marker_pair_min, d)
            if d < 140:
                issues.append(f"live markers {an} / {bn} separation {d:.1f} < 140")

    required_goals = {name: pos for name, pos in layout["markers"].items() if name.startswith(("enemy_", "comp_", "boss", "civilian_")) or name in {"extraction", "artifact", "reroute_extraction"}}
    reached = reachable(layout["markers"]["entry"], required_goals, all_parts)
    missing_routes = sorted(set(required_goals) - reached)
    if missing_routes:
        issues.append("unreachable markers for max-radius actor: " + ", ".join(missing_routes))

    destructible = [o for o in physical if o["destructible"]]
    corner_count = sum(1 for o in physical if o["category"] == "corner")
    if not destructible:
        issues.append("no destructible cover")
    if not corner_count:
        issues.append("no corner cover")

    return {
        "quest": key,
        "layout": layout["name"],
        "world_rect": WORLD_RECT,
        "physical_objects": len(physical),
        "collision_parts": len(all_parts),
        "destructible_cover": len(destructible),
        "corner_cover": corner_count,
        "minimum_object_gap": round(min(pair_distances) if pair_distances else 9999.0, 2),
        "marker_clearance": marker_checks,
        "minimum_live_marker_gap": round(marker_pair_min, 2),
        "max_actor_radius": MAX_ACTOR_RADIUS,
        "all_required_routes_reachable": not missing_routes,
        "issues": issues,
        "pass": not issues,
    }


def main() -> int:
    reports = [validate_layout(key) for key in LAYOUTS]
    payload = {
        "pass14_world_contract": "PASS" if all(row["pass"] for row in reports) else "FAIL",
        "world_rect": WORLD_RECT,
        "minimum_clear_gap": MIN_CLEAR_GAP,
        "spawn_clearance": SPAWN_CLEARANCE,
        "layouts": reports,
    }
    out = ROOT / "verification" / "reports" / "pass14_world_geometry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["pass14_world_contract"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
