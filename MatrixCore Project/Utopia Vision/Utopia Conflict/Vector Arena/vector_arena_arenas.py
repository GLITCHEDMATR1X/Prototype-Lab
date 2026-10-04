"""Pure-Python arena family, scale, architecture, and navigation rules.

Pass 07 makes each arena family structurally distinct while keeping one hard
contract: rendered solid architecture and gameplay blocking geometry derive from
the same authored pieces.  There are no decorative invisible blockers and no
visual cover pieces that gameplay silently ignores.
"""
from __future__ import annotations

from collections import deque
from math import hypot

BASE_ARENA_RADIUS = 118.0
MAX_ARENA_RADIUS = 228.0
ARENA_GROWTH_PER_SET = 22.0
PLAYER_CLEARANCE = 5.5
GATE_CLEARANCE = 10.0
OBJECTIVE_CLEARANCE = 6.0
HAZARD_CLEARANCE = 5.0

ARENA_FAMILIES = (
    {
        "id": "PRISM_FOUNDRY", "name": "PRISM FOUNDRY",
        "wire_primary": (0.18, 1.00, 0.86, 0.82),
        "wire_secondary": (1.00, 0.78, 0.18, 0.72),
        "wire_accent": (1.00, 0.22, 0.92, 0.66),
        "floor": (0.010, 0.025, 0.034, 0.93), "sky": (0.002, 0.004, 0.010),
        "grid_step": 12.0, "cover_spread": 1.00,
        "architecture": "FOUNDRY_PILLARS",
    },
    {
        "id": "NEON_CANYON", "name": "NEON CANYON",
        "wire_primary": (1.00, 0.36, 0.12, 0.84),
        "wire_secondary": (1.00, 0.18, 0.88, 0.72),
        "wire_accent": (0.38, 0.92, 1.00, 0.68),
        "floor": (0.032, 0.016, 0.010, 0.93), "sky": (0.018, 0.004, 0.012),
        "grid_step": 14.0, "cover_spread": 1.12,
        "architecture": "CANYON_WALLS",
    },
    {
        "id": "FROST_CIRCUIT", "name": "FROST CIRCUIT",
        "wire_primary": (0.46, 0.86, 1.00, 0.84),
        "wire_secondary": (0.86, 1.00, 1.00, 0.72),
        "wire_accent": (0.24, 0.34, 1.00, 0.66),
        "floor": (0.006, 0.020, 0.034, 0.93), "sky": (0.001, 0.008, 0.018),
        "grid_step": 16.0, "cover_spread": 1.22,
        "architecture": "CRYSTAL_BARRIERS",
    },
    {
        "id": "DATA_STORM", "name": "DATA STORM",
        "wire_primary": (0.30, 1.00, 0.38, 0.84),
        "wire_secondary": (0.18, 1.00, 0.92, 0.74),
        "wire_accent": (1.00, 1.00, 0.24, 0.68),
        "floor": (0.006, 0.030, 0.018, 0.93), "sky": (0.002, 0.014, 0.006),
        "grid_step": 18.0, "cover_spread": 1.34,
        "architecture": "BROKEN_DATA_WALLS",
    },
    {
        "id": "REDLINE_CORE", "name": "REDLINE COLOSSUS",
        "wire_primary": (1.00, 0.16, 0.18, 0.86),
        "wire_secondary": (1.00, 0.52, 0.14, 0.74),
        "wire_accent": (0.94, 0.22, 1.00, 0.70),
        "floor": (0.034, 0.006, 0.010, 0.93), "sky": (0.018, 0.002, 0.004),
        "grid_step": 20.0, "cover_spread": 1.48,
        "architecture": "COLOSSUS_MONOLITHS",
    },
)

# Positions are normalized against the current arena radius.  Half extents are
# authored in world units and only grow modestly as arena size increases.  Each
# tuple: x_norm, y_norm, half_x, half_y, half_z, visual_style.
_ARCHITECTURE = {
    "PRISM_FOUNDRY": (
        (-0.28,-0.20, 7.0, 7.0, 9.0,"pillar"), (0.28,-0.20, 7.0, 7.0, 9.0,"pillar"),
        (-0.42, 0.02,10.0, 5.0, 4.0,"machine"),(0.42, 0.02,10.0, 5.0, 4.0,"machine"),
        (-0.22, 0.28, 7.0, 7.0,10.0,"pillar"), (0.22, 0.28, 7.0, 7.0,10.0,"pillar"),
        ( 0.00, 0.17, 5.0,10.0, 5.0,"reactor"),
        (-0.48, 0.30, 8.0, 4.0, 4.0,"machine"),(0.48, 0.30, 8.0, 4.0, 4.0,"machine"),
        ( 0.00,-0.50,14.0, 4.0, 5.0,"machine"),
    ),
    "NEON_CANYON": (
        (-0.34,-0.28,18.0, 4.0, 6.0,"canyon_wall"),(0.34,-0.28,18.0, 4.0, 6.0,"canyon_wall"),
        (-0.48, 0.02, 4.0,18.0, 7.0,"canyon_wall"),(0.48, 0.02, 4.0,18.0, 7.0,"canyon_wall"),
        (-0.22, 0.25,16.0, 4.0, 6.0,"canyon_wall"),(0.22, 0.25,16.0, 4.0, 6.0,"canyon_wall"),
        ( 0.00, 0.42,22.0, 4.0, 8.0,"canyon_wall"),
        ( 0.00, 0.16, 5.0,11.0, 5.0,"relay_tower"),
    ),
    "FROST_CIRCUIT": (
        (-0.36,-0.25,16.0,3.5, 7.0,"crystal"),(0.36,-0.25,16.0,3.5, 7.0,"crystal"),
        (-0.50, 0.10, 3.5,14.0,8.0,"crystal"),(0.50, 0.10, 3.5,14.0,8.0,"crystal"),
        (-0.26, 0.32,14.0,3.5, 8.0,"crystal"),(0.26, 0.32,14.0,3.5, 8.0,"crystal"),
        ( 0.00, 0.15, 4.0,13.0,10.0,"frost_spire"),
        ( 0.00, 0.48,18.0,3.5, 7.0,"crystal"),
    ),
    "DATA_STORM": (
        (-0.44,-0.28,10.0,4.0,6.0,"data_segment"),(-0.20,-0.28,8.0,4.0,6.0,"data_segment"),
        ( 0.20,-0.28, 8.0,4.0,6.0,"data_segment"),( 0.44,-0.28,10.0,4.0,6.0,"data_segment"),
        (-0.48, 0.08, 4.0,10.0,7.0,"data_segment"),(-0.48,0.34,4.0,8.0,7.0,"data_segment"),
        ( 0.48, 0.08, 4.0,10.0,7.0,"data_segment"),( 0.48,0.34,4.0,8.0,7.0,"data_segment"),
        (-0.18, 0.28, 8.0,4.0,7.0,"data_segment"),( 0.18,0.28,8.0,4.0,7.0,"data_segment"),
        ( 0.00, 0.10, 5.0,5.0,10.0,"data_node"),
    ),
    "REDLINE_CORE": (
        (-0.32,-0.22,12.0,12.0,14.0,"monolith"),(0.32,-0.22,12.0,12.0,14.0,"monolith"),
        (-0.32, 0.24,12.0,12.0,16.0,"monolith"),(0.32, 0.24,12.0,12.0,16.0,"monolith"),
        ( 0.00,-0.50,20.0, 5.0, 8.0,"bastion"),
        (-0.55, 0.02, 5.0,18.0,10.0,"bastion"),(0.55,0.02,5.0,18.0,10.0,"bastion"),
        ( 0.00, 0.50,20.0, 5.0,10.0,"bastion"),
    ),
}

_GATE_NORMALIZED = (
    (-0.54, 0.46),(0.00, 0.58),(0.54, 0.46),(-0.66,-0.03),(0.66,-0.03),(-0.34,-0.44),(0.34,-0.44),
)
_BREACH_NORMALIZED = (
    (-0.46,0.22),(0.46,0.22),(-0.37,-0.20),(0.37,-0.20),(0.00,0.39),(0.00,-0.32),(-0.63,0.07),(0.63,0.07),
)
_HAZARD_NORMALIZED = (
    (-0.36,-0.24),(0.36,-0.24),(-0.46,0.15),(0.46,0.15),(0.00,0.03),(-0.19,0.37),(0.19,0.37),(0.00,-0.40),
)


def arena_profile_for_set(set_number: int) -> dict:
    set_number = max(1, int(set_number))
    family = dict(ARENA_FAMILIES[(set_number - 1) % len(ARENA_FAMILIES)])
    radius = min(MAX_ARENA_RADIUS, BASE_ARENA_RADIUS + (set_number - 1) * ARENA_GROWTH_PER_SET)
    family.update({
        "set_number": set_number, "radius": float(radius), "diameter": float(radius * 2.0),
        "area_ratio": float((radius / BASE_ARENA_RADIUS) ** 2), "scale_ratio": float(radius / BASE_ARENA_RADIUS),
        "is_max_size": bool(radius >= MAX_ARENA_RADIUS),
    })
    return family


def _structure_scale(profile: dict) -> float:
    return 1.0 + (float(profile["scale_ratio"]) - 1.0) * 0.35


def architecture_pieces_for_profile(profile: dict) -> list[dict]:
    radius = float(profile["radius"])
    size_scale = _structure_scale(profile)
    authored = _ARCHITECTURE[str(profile["id"])]
    pieces = []
    for index, (nx, ny, hx, hy, hz, style) in enumerate(authored):
        pieces.append({
            "id": f"{str(profile['id']).lower()}_{index:02d}",
            "x": float(nx * radius), "y": float(ny * radius),
            "half_x": float(hx * size_scale), "half_y": float(hy * size_scale), "half_z": float(hz),
            "style": str(style),
        })
    return pieces


def spawn_points_for_profile(profile: dict) -> list[tuple[float,float]]:
    radius = float(profile["radius"])
    return [(x * radius, y * radius) for x, y in _GATE_NORMALIZED]


def _point_inside_piece(point: tuple[float,float], piece: dict, clearance: float = 0.0) -> bool:
    x, y = point
    return abs(x - float(piece["x"])) <= float(piece["half_x"]) + clearance and abs(y - float(piece["y"])) <= float(piece["half_y"]) + clearance


def _resolve_safe_point(seed: tuple[float,float], profile: dict, clearance: float) -> tuple[float,float]:
    """Move a seed only when authored architecture would occupy it.

    Search is deterministic and local: the original design point is kept whenever
    it is legal; otherwise the nearest 4-unit lattice candidate is selected.
    """
    radius = float(profile["radius"])
    pieces = architecture_pieces_for_profile(profile)
    sx, sy = seed
    if hypot(sx, sy) < radius - 16.0 and not any(_point_inside_piece(seed, p, clearance) for p in pieces):
        return float(sx), float(sy)
    step = 4.0
    for ring in range(1, 17):
        candidates = []
        for ix in range(-ring, ring + 1):
            for iy in range(-ring, ring + 1):
                if max(abs(ix), abs(iy)) != ring:
                    continue
                x, y = sx + ix * step, sy + iy * step
                if hypot(x, y) >= radius - 16.0:
                    continue
                if any(_point_inside_piece((x, y), p, clearance) for p in pieces):
                    continue
                candidates.append((ix * ix + iy * iy, x, y))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            _, x, y = candidates[0]
            return float(x), float(y)
    raise ValueError(f"No safe strategic point near {seed} in {profile['id']}")


def breach_points_for_profile(profile: dict) -> list[tuple[float,float]]:
    ratio = 1.0 + (float(profile["scale_ratio"]) - 1.0) * 0.82
    seed_radius = BASE_ARENA_RADIUS * ratio
    return [_resolve_safe_point((x * seed_radius, y * seed_radius), profile, OBJECTIVE_CLEARANCE) for x, y in _BREACH_NORMALIZED]


def hazard_points_for_profile(profile: dict) -> list[tuple[float,float]]:
    radius = float(profile["radius"])
    return [_resolve_safe_point((x * radius, y * radius), profile, HAZARD_CLEARANCE) for x, y in _HAZARD_NORMALIZED]


def cover_scale_for_profile(profile: dict) -> float:
    """Legacy compatibility only; Pass 07 architecture no longer uses layout spreading."""
    return 1.0



def first_architecture_hit(profile: dict, start: tuple[float,float,float], end: tuple[float,float,float]) -> dict | None:
    """Return the first solid architecture hit along a 3D segment.

    This is the hitscan authority used by Pass 07.  Each obstacle occupies the
    same XY extents as its visible solid and extends from floor Z=0 to its
    authored full height (2 * half_z).  It therefore cannot create a shot-blocking
    region that the player cannot see.
    """
    sx, sy, sz = (float(v) for v in start)
    ex, ey, ez = (float(v) for v in end)
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    best = None
    for piece in architecture_pieces_for_profile(profile):
        bounds = (
            (float(piece['x']) - float(piece['half_x']), float(piece['x']) + float(piece['half_x']), sx, dx),
            (float(piece['y']) - float(piece['half_y']), float(piece['y']) + float(piece['half_y']), sy, dy),
            (0.0, float(piece['half_z']) * 2.0, sz, dz),
        )
        t0, t1 = 0.0, 1.0
        valid = True
        for lo, hi, origin, delta in bounds:
            if abs(delta) < 1e-9:
                if origin < lo or origin > hi:
                    valid = False; break
                continue
            a = (lo - origin) / delta; b = (hi - origin) / delta
            if a > b: a, b = b, a
            t0 = max(t0, a); t1 = min(t1, b)
            if t0 > t1:
                valid = False; break
        if not valid or t1 < 0.0 or t0 > 1.0:
            continue
        t = max(0.0, t0)
        if best is None or t < best['t']:
            best = {
                't': float(t), 'piece_id': str(piece['id']), 'style': str(piece['style']),
                'point': (sx + dx * t, sy + dy * t, sz + dz * t),
            }
    return best

def _pieces_overlap(a: dict, b: dict, pad: float = 4.0) -> bool:
    return abs(float(a["x"]) - float(b["x"])) < float(a["half_x"]) + float(b["half_x"]) + pad and abs(float(a["y"]) - float(b["y"])) < float(a["half_y"]) + float(b["half_y"]) + pad


def _reachable_contract(profile: dict, clearance: float = PLAYER_CLEARANCE, grid_step: float = 4.0) -> dict:
    radius = float(profile["radius"])
    pieces = architecture_pieces_for_profile(profile)
    xmin = -radius
    count = int((2.0 * radius) // grid_step) + 2
    free = set()
    for ix in range(count):
        x = xmin + ix * grid_step
        for iy in range(count):
            y = xmin + iy * grid_step
            if hypot(x, y) > radius - 7.0:
                continue
            if any(_point_inside_piece((x, y), p, clearance) for p in pieces):
                continue
            free.add((ix, iy))

    def nearest(point: tuple[float,float]):
        px, py = point
        ix = round((px - xmin) / grid_step); iy = round((py - xmin) / grid_step)
        if (ix, iy) in free:
            return ix, iy
        for ring in range(1, 10):
            candidates = []
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    cell = (ix + dx, iy + dy)
                    if cell in free:
                        candidates.append((dx * dx + dy * dy, cell))
            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1]))
                return candidates[0][1]
        return None

    start = nearest((0.0, 0.0))
    if start is None:
        return {"reachable": False, "reachable_cells": 0, "unreachable": ["CENTER"]}
    seen = {start}; queue = deque([start])
    while queue:
        cell = queue.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt in free and nxt not in seen:
                seen.add(nxt); queue.append(nxt)

    targets = [("GATE", i, p) for i, p in enumerate(spawn_points_for_profile(profile))]
    targets += [("BREACH", i, p) for i, p in enumerate(breach_points_for_profile(profile))]
    targets += [("HAZARD", i, p) for i, p in enumerate(hazard_points_for_profile(profile))]
    unreachable = []
    for kind, index, point in targets:
        cell = nearest(point)
        if cell is None or cell not in seen:
            unreachable.append(f"{kind}_{index}")
    return {"reachable": not unreachable, "reachable_cells": len(seen), "unreachable": unreachable}


def validate_architecture(profile: dict) -> dict:
    radius = float(profile["radius"])
    pieces = architecture_pieces_for_profile(profile)
    overlaps = []
    for i, a in enumerate(pieces):
        for j in range(i + 1, len(pieces)):
            if _pieces_overlap(a, pieces[j], 4.0):
                overlaps.append((i, j))
    center_conflicts = [i for i, piece in enumerate(pieces) if _point_inside_piece((0.0, 0.0), piece, PLAYER_CLEARANCE)]
    gate_conflicts = []
    for gi, point in enumerate(spawn_points_for_profile(profile)):
        for pi, piece in enumerate(pieces):
            if _point_inside_piece(point, piece, GATE_CLEARANCE):
                gate_conflicts.append((gi, pi))
    boundary_conflicts = []
    for i, piece in enumerate(pieces):
        outer = hypot(float(piece["x"]), float(piece["y"])) + hypot(float(piece["half_x"]), float(piece["half_y"]))
        if outer >= radius - 8.0:
            boundary_conflicts.append(i)
    objective_conflicts = [
        (i, pi) for i, point in enumerate(breach_points_for_profile(profile)) for pi, piece in enumerate(pieces)
        if _point_inside_piece(point, piece, OBJECTIVE_CLEARANCE - 0.1)
    ]
    hazard_conflicts = [
        (i, pi) for i, point in enumerate(hazard_points_for_profile(profile)) for pi, piece in enumerate(pieces)
        if _point_inside_piece(point, piece, HAZARD_CLEARANCE - 0.1)
    ]
    route = _reachable_contract(profile)
    return {
        "family": profile["id"], "architecture": profile["architecture"], "piece_count": len(pieces),
        "overlaps": overlaps, "center_conflicts": center_conflicts, "gate_conflicts": gate_conflicts, "boundary_conflicts": boundary_conflicts,
        "objective_conflicts": objective_conflicts, "hazard_conflicts": hazard_conflicts,
        "routes_reachable": bool(route["reachable"]), "unreachable_targets": route["unreachable"],
        "reachable_cells": route["reachable_cells"],
    }


def validate_profiles() -> dict:
    samples = [arena_profile_for_set(i) for i in range(1, 31)]
    radii = [item["radius"] for item in samples]
    architecture = [validate_architecture(item) for item in samples]
    return {
        "family_count": len(ARENA_FAMILIES), "set_1_radius": radii[0], "set_5_radius": radii[4],
        "set_6_radius": radii[5], "set_30_radius": radii[-1],
        "nondecreasing_radius": all(a <= b for a, b in zip(radii, radii[1:])),
        "max_radius_respected": max(radii) <= MAX_ARENA_RADIUS,
        "families_seen": sorted({item["id"] for item in samples}),
        "architectures_seen": sorted({item["architecture"] for item in samples}),
        "architecture_all_clear": all(not a["overlaps"] and not a["center_conflicts"] and not a["gate_conflicts"] and not a["boundary_conflicts"] and not a["objective_conflicts"] and not a["hazard_conflicts"] and a["routes_reachable"] for a in architecture),
    }
