from __future__ import annotations

"""Pure machine-building economy and connectivity helpers for Afterlife of IO.

Pass 102 established Bits, a data-driven Sable catalogue and persistent loose
placements. Pass 103 added a deliberately small contact-powered machine graph.
Pass 119 keeps the deterministic contact graph but treats the Conduit Pipe as a
fixed-length rigid link. One endpoint forms a persistent pin/hinge on the driven
Pivot/Gear contact point; the opposite endpoint may form a second persistent
hinge on a movable machine component. The link never stretches or compresses.

The module deliberately avoids pygame so GXTool/static tests can validate the
rules without requiring an SDL runtime.
"""

from math import hypot, cos, sin, radians, atan2, degrees
from typing import Iterable, Mapping

BITS_STORY_WIN = 12
BITS_ECHO_WIN = 6
BITS_FINAL_WIN = 18
BITS_DEFEAT_LOSS = 2
DEFAULT_MACHINE_COST = 5
DEFAULT_MACHINE_WORLD_HEIGHT = 82.0
DEFAULT_MACHINE_TOUCH_RADIUS_RATIO = 0.50
MAX_BITS = 99999
MAX_MACHINE_PLACEMENTS = 256
MAX_MACHINE_STACK = 99

ROLE_CORE = "core"
ROLE_GEAR = "gear"
ROLE_PIVOT = "pivot"
ROLE_FAN = "fan"
ROLE_PIPE = "pipe"
ROLE_FRAME = "frame"
ROLE_COSMETIC = "cosmetic"
ROLE_HEAD = "head"
ROLE_ACTUATOR = "actuator"
ROLE_SENSOR = "sensor"
ROLE_TOOL = "tool"
KNOWN_MACHINE_ROLES = {
    ROLE_CORE,
    ROLE_GEAR,
    ROLE_PIVOT,
    ROLE_FAN,
    ROLE_PIPE,
    ROLE_FRAME,
    ROLE_COSMETIC,
    ROLE_HEAD,
    ROLE_ACTUATOR,
    ROLE_SENSOR,
    ROLE_TOOL,
}

AUTONOMOUS_MOTION_REQUIRED_ROLES = (
    ROLE_CORE,
    ROLE_GEAR,
    ROLE_PIVOT,
    ROLE_ACTUATOR,
)

# Pass 119 rigid Pipe constraints. The replaceable pipe PNG is a fixed-size,
# horizontal left-to-right rigid link in local space. Its authored aspect ratio
# and endpoint separation never change at runtime.
PIPE_ENDPOINT_OFFSET_WORLD = 41.0
PIPE_ENDPOINT_ATTACH_RADIUS_WORLD = 22.0
# A loose Pipe may begin moving only when one of its visible endpoints is actually
# on the driven Gear/Pivot surface.  This small allowance compensates for
# transparent padding in replaceable PNGs without restoring the old center-radius
# false positives when a rotated Pipe is visibly far away.
PIPE_GEAR_CONTACT_SLOP_WORLD = 6.0
PIPE_BRACE_ATTACH_RADIUS_WORLD = 18.0
PIPE_END_LEFT = "left"
PIPE_END_RIGHT = "right"
PIPE_BRACE_ROLES = {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT, ROLE_FRAME, ROLE_COSMETIC}
# Pass 129: when a fabricated part has authored sockets, those sockets become
# the contact authority for Core/Gear/Pivot drive assembly.  The magnetic drag
# assist uses a slightly larger radius; this tighter threshold is the actual
# connection tolerance after placement.  Legacy parts with no sockets keep the
# proven center/radius contact behavior.
SOCKET_CONTACT_RADIUS_WORLD = 12.0
# Pass 143: accessory sockets are a visual/mechanical agreement layer.  They
# affect only HEAD/ACTUATOR/SENSOR/TOOL attachment adjacency; the proven
# Core/Gear/Pivot triangle and rigid Pipe/Fan solvers retain their own rules.
ACCESSORY_SOCKET_CONTACT_RADIUS_WORLD = 14.0


def normalize_pipe_end(value: object, default: str = PIPE_END_LEFT) -> str:
    end = str(value or "").strip().lower()
    return end if end in {PIPE_END_LEFT, PIPE_END_RIGHT} else default


def opposite_pipe_end(value: object) -> str:
    return PIPE_END_RIGHT if normalize_pipe_end(value) == PIPE_END_LEFT else PIPE_END_LEFT


def pipe_direction(angle_degrees: float) -> tuple[float, float]:
    """Left-to-right unit vector for a sprite angle in y-down world space."""
    r = radians(float(angle_degrees))
    return cos(r), -sin(r)


def pipe_endpoints(
    center_x: float, center_y: float, angle_degrees: float, length: float | None = None
) -> dict[str, tuple[float, float]]:
    total = max(1.0, float(length if length is not None else PIPE_ENDPOINT_OFFSET_WORLD * 2.0))
    half = total * 0.5
    dx, dy = pipe_direction(angle_degrees)
    return {
        PIPE_END_LEFT: (float(center_x) - dx * half, float(center_y) - dy * half),
        PIPE_END_RIGHT: (float(center_x) + dx * half, float(center_y) + dy * half),
    }


def pipe_pose_between(ax: float, ay: float, bx: float, by: float) -> tuple[float, float, float, float]:
    """Return center x/y, sprite angle and endpoint distance for two constraints."""
    dx = float(bx) - float(ax)
    dy = float(by) - float(ay)
    length = max(1.0, hypot(dx, dy))
    # pygame-style positive angles are counter-clockwise while world y points down.
    angle = degrees(atan2(-dy, dx)) % 360.0
    return (float(ax) + float(bx)) * 0.5, (float(ay) + float(by)) * 0.5, angle, length


def clamp_machine_stack(value: object) -> int:
    try:
        amount = int(value)
    except (TypeError, ValueError, OverflowError):
        amount = 0
    return max(0, min(MAX_MACHINE_STACK, amount))


def sanitize_machine_inventory(raw: object, *, valid_part_keys: set[str]) -> dict[str, int]:
    """Return a complete bounded inventory for all currently discoverable machine parts."""
    source = raw if isinstance(raw, Mapping) else {}
    return {key: clamp_machine_stack(source.get(key, 0)) for key in sorted(valid_part_keys)}


def add_machine_item(inventory: Mapping[str, object] | None, part_key: str, amount: int = 1) -> dict[str, int]:
    result = {str(key): clamp_machine_stack(value) for key, value in (inventory or {}).items()}
    key = str(part_key)
    result[key] = clamp_machine_stack(result.get(key, 0) + int(amount))
    return result


def consume_machine_item(inventory: Mapping[str, object] | None, part_key: str, amount: int = 1) -> tuple[dict[str, int], bool]:
    result = {str(key): clamp_machine_stack(value) for key, value in (inventory or {}).items()}
    key = str(part_key)
    needed = max(1, int(amount))
    current = clamp_machine_stack(result.get(key, 0))
    if current < needed:
        result[key] = current
        return result, False
    result[key] = current - needed
    return result, True


def grant_all_machine_items(valid_part_keys: set[str], *, count: int = MAX_MACHINE_STACK) -> dict[str, int]:
    granted = clamp_machine_stack(count)
    return {key: granted for key in sorted(valid_part_keys)}


def clamp_bits(value: object) -> int:
    try:
        amount = int(value)
    except (TypeError, ValueError, OverflowError):
        amount = 0
    return max(0, min(MAX_BITS, amount))


def victory_bits(*, rematch: bool, final_guardian: bool = False) -> int:
    if rematch:
        return BITS_ECHO_WIN
    if final_guardian:
        return BITS_FINAL_WIN
    return BITS_STORY_WIN


def defeat_bits_loss(current_bits: object) -> int:
    return min(clamp_bits(current_bits), BITS_DEFEAT_LOSS)


def migrated_legacy_bits(
    defeated_entities: Iterable[object] | None,
    challenge_wins: Mapping[object, object] | None,
    *,
    final_guardian_id: str = "null_custodian",
) -> int:
    """Credit old saves once for victories earned before Bits existed."""
    defeated = {str(value) for value in (defeated_entities or []) if str(value)}
    total = 0
    for entity_id in defeated:
        total += victory_bits(rematch=False, final_guardian=(entity_id == final_guardian_id))
    if isinstance(challenge_wins, Mapping):
        for value in challenge_wins.values():
            try:
                wins = max(0, int(value))
            except (TypeError, ValueError, OverflowError):
                wins = 0
            total += wins * BITS_ECHO_WIN
    return clamp_bits(total)


def sanitize_machine_placements(
    raw: object,
    *,
    valid_part_keys: set[str],
    world_width: float,
    world_height: float,
) -> list[dict]:
    if not isinstance(raw, list):
        return []
    clean: list[dict] = []
    seen_ids: set[int] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        part = str(item.get("part", "")).strip()
        world = str(item.get("world", "")).strip().lower()
        if part not in valid_part_keys or world not in {"a", "b"}:
            continue
        try:
            instance_id = int(item.get("id", 0))
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            walk_layer = int(item.get("walk_layer", 0))
            angle = float(item.get("angle", 0.0))
            flip_x = bool(item.get("flip_x", False))
            attach_phase_raw = item.get("attach_phase", None)
            attach_phase = None if attach_phase_raw is None else float(attach_phase_raw)
            attach_dx_raw = item.get("attach_local_dx", None)
            attach_dy_raw = item.get("attach_local_dy", None)
            attach_local_dx = None if attach_dx_raw is None else float(attach_dx_raw)
            attach_local_dy = None if attach_dy_raw is None else float(attach_dy_raw)
            pipe_anchor_end_raw = item.get("pipe_anchor_end", None)
            pipe_anchor_end = None if pipe_anchor_end_raw is None else normalize_pipe_end(pipe_anchor_end_raw)
            pipe_hinge_id_raw = item.get("pipe_hinge_id", None)
            pipe_hinge_id = None if pipe_hinge_id_raw is None else int(pipe_hinge_id_raw)
            pipe_orbit_dir_raw = item.get("pipe_orbit_dir", None)
            pipe_orbit_dir = None if pipe_orbit_dir_raw is None else int(pipe_orbit_dir_raw)
            pipe_brace_id_raw = item.get("pipe_brace_id", None)
            pipe_brace_id = None if pipe_brace_id_raw is None else int(pipe_brace_id_raw)
            pipe_brace_dx_raw = item.get("pipe_brace_local_dx", None)
            pipe_brace_dy_raw = item.get("pipe_brace_local_dy", None)
            pipe_brace_local_dx = None if pipe_brace_dx_raw is None else float(pipe_brace_dx_raw)
            pipe_brace_local_dy = None if pipe_brace_dy_raw is None else float(pipe_brace_dy_raw)
            pipe_brace_angle_raw = item.get("pipe_brace_angle", None)
            pipe_brace_angle = None if pipe_brace_angle_raw is None else float(pipe_brace_angle_raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if instance_id <= 0 or instance_id in seen_ids:
            continue
        seen_ids.add(instance_id)
        x = max(0.0, min(float(world_width), x))
        y = max(0.0, min(float(world_height), y))
        clean.append({
            "id": instance_id,
            "part": part,
            "world": world,
            "walk_layer": walk_layer,
            "x": round(x, 3),
            "y": round(y, 3),
            "angle": round(angle % 360.0, 3),
            "flip_x": flip_x,
            **({"attach_phase": round(attach_phase % 360.0, 3)} if attach_phase is not None else {}),
            **({"attach_local_dx": round(attach_local_dx, 3), "attach_local_dy": round(attach_local_dy, 3)} if attach_local_dx is not None and attach_local_dy is not None else {}),
            **({"pipe_anchor_end": pipe_anchor_end} if pipe_anchor_end is not None else {}),
            **({"pipe_hinge_id": pipe_hinge_id} if pipe_hinge_id is not None and pipe_hinge_id > 0 else {}),
            **({"pipe_orbit_dir": 1 if pipe_orbit_dir is not None and pipe_orbit_dir >= 0 else -1} if pipe_orbit_dir is not None else {}),
            **({"pipe_brace_id": pipe_brace_id} if pipe_brace_id is not None and pipe_brace_id > 0 else {}),
            **({"pipe_brace_local_dx": round(pipe_brace_local_dx, 3), "pipe_brace_local_dy": round(pipe_brace_local_dy, 3)} if pipe_brace_local_dx is not None and pipe_brace_local_dy is not None else {}),
            **({"pipe_brace_angle": round(pipe_brace_angle % 360.0, 3)} if pipe_brace_angle is not None else {}),
        })
        if len(clean) >= MAX_MACHINE_PLACEMENTS:
            break
    return clean


def normalize_machine_role(value: object) -> str:
    role = str(value or "").strip().lower()
    return role if role in KNOWN_MACHINE_ROLES else ROLE_COSMETIC


def autonomous_motion_requirements(roles: Iterable[object], *, powered_drive: bool) -> dict[str, object]:
    """Return a compact, deterministic mobility diagnostic for a machine head.

    The HEAD is the control/communication component.  Independent movement is
    deliberately *not* enabled here; this helper only reports whether the
    hardware package needed by a future locomotion system is physically present.
    """
    present = {normalize_machine_role(value) for value in roles}
    missing = tuple(role for role in AUTONOMOUS_MOTION_REQUIRED_ROLES if role not in present)
    return {
        "head_present": ROLE_HEAD in present,
        "present_roles": tuple(sorted(present)),
        "missing_roles": missing,
        "hardware_complete": not missing,
        "powered_drive": bool(powered_drive),
        "ready_for_autonomy": bool(not missing and powered_drive and ROLE_HEAD in present),
    }


def _machine_scope(item: Mapping[str, object]) -> tuple[str, int]:
    try:
        walk_layer = int(item.get("walk_layer", 0))
    except (TypeError, ValueError, OverflowError):
        walk_layer = 0
    return str(item.get("world", "")).strip().lower(), walk_layer


def _machine_xy(item: Mapping[str, object]) -> tuple[float, float]:
    try:
        return float(item.get("x", 0.0)), float(item.get("y", 0.0))
    except (TypeError, ValueError, OverflowError):
        return 0.0, 0.0


def _machine_angle(item: Mapping[str, object]) -> float:
    try:
        return float(item.get("angle", 0.0)) % 360.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _machine_id(item: Mapping[str, object]) -> int:
    try:
        return int(item.get("id", 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _distance(a: Mapping[str, object], b: Mapping[str, object]) -> float:
    ax, ay = _machine_xy(a)
    bx, by = _machine_xy(b)
    return hypot(ax - bx, ay - by)


def resolve_machine_network(
    placements: Iterable[Mapping[str, object]],
    *,
    part_roles: Mapping[str, str],
    part_touch_radii: Mapping[str, float],
    contact_points_by_id: Mapping[int, Iterable[tuple[float, float]]] | None = None,
    accessory_contact_points_by_id: Mapping[int, Iterable[tuple[float, float]]] | None = None,
    exclude_ids: Iterable[int] | None = None,
) -> dict[int, dict[str, object]]:
    """Resolve the contact-powered machine graph.

    A pivot is powered only when the *same* triangle of parts satisfies all of
    these contacts in one era/walk layer:

      CORE <-> GEAR
      CORE <-> PIVOT
      GEAR <-> PIVOT

    That deliberately implements the user's rule that both the gear and pivot
    need the Core Housing, while the gear is still required to drive the pivot.
    Pass 129 adds one narrow refinement: if either participating drive part has
    explicit authored sockets, those world-space sockets become the contact
    authority instead of the old broad center-radius test. Legacy parts without
    sockets remain byte-for-behavior compatible with the earlier rule.
    Pass 143 adds a second, separate point set for powered accessories so a HEAD,
    ACTUATOR, SENSOR or TOOL that magnetically snaps to a visible connector uses
    that same connector for power adjacency.  Drive-drive, Pipe and Fan behavior
    is intentionally unchanged.
    Pipes attach to the nearest powered pivot they physically touch. Fans prefer a
    powered pipe endpoint when one is close enough, otherwise they can still spin
    directly on a powered pivot. Frame plates never transmit power, but a plate
    touching a powered drive receives a presentation-only ticking state.
    """
    excluded = {int(value) for value in (exclude_ids or ())}
    items: dict[int, Mapping[str, object]] = {}
    roles: dict[int, str] = {}
    radii: dict[int, float] = {}

    for raw in placements:
        instance_id = _machine_id(raw)
        if instance_id <= 0 or instance_id in excluded:
            continue
        part_key = str(raw.get("part", "")).strip()
        role = normalize_machine_role(part_roles.get(part_key, ROLE_COSMETIC))
        try:
            radius = max(1.0, float(part_touch_radii.get(part_key, 1.0)))
        except (TypeError, ValueError, OverflowError):
            radius = 1.0
        items[instance_id] = raw
        roles[instance_id] = role
        radii[instance_id] = radius

    # Optional explicit socket positions are supplied by the renderer/gameplay
    # layer because it knows each part's authored image dimensions, rotation and
    # flip.  The pure machine resolver only needs world-space points.
    explicit_points: dict[int, tuple[tuple[float, float], ...]] = {}
    if isinstance(contact_points_by_id, Mapping):
        for raw_id, raw_points in contact_points_by_id.items():
            try:
                instance_id = int(raw_id)
            except (TypeError, ValueError, OverflowError):
                continue
            if instance_id not in items:
                continue
            clean_points: list[tuple[float, float]] = []
            try:
                iterator = iter(raw_points)
            except TypeError:
                continue
            for value in iterator:
                if not isinstance(value, (tuple, list)) or len(value) < 2:
                    continue
                try:
                    clean_points.append((float(value[0]), float(value[1])))
                except (TypeError, ValueError, OverflowError):
                    continue
            if clean_points:
                explicit_points[instance_id] = tuple(clean_points)

    accessory_points: dict[int, tuple[tuple[float, float], ...]] = {}
    if isinstance(accessory_contact_points_by_id, Mapping):
        for raw_id, raw_points in accessory_contact_points_by_id.items():
            try:
                instance_id = int(raw_id)
            except (TypeError, ValueError, OverflowError):
                continue
            if instance_id not in items:
                continue
            clean_points: list[tuple[float, float]] = []
            try:
                iterator = iter(raw_points)
            except TypeError:
                continue
            for value in iterator:
                if not isinstance(value, (tuple, list)) or len(value) < 2:
                    continue
                try:
                    clean_points.append((float(value[0]), float(value[1])))
                except (TypeError, ValueError, OverflowError):
                    continue
            if clean_points:
                accessory_points[instance_id] = tuple(clean_points)

    def drive_contact(left_id: int, right_id: int) -> bool:
        # Socket authority is deliberately limited to the Core/Gear/Pivot drive
        # triangle. Pipe/Fan attachment keeps the established center/radius path
        # so Pass 129 cannot rewrite rigid Conduit or fan behavior by accident.
        drive_roles = {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT}
        if roles.get(left_id) not in drive_roles or roles.get(right_id) not in drive_roles:
            return _distance(items[left_id], items[right_id]) <= radii[left_id] + radii[right_id]
        left_points = explicit_points.get(left_id)
        right_points = explicit_points.get(right_id)
        # If neither drive part opts into authored sockets, preserve the established
        # center/radius contact contract exactly.
        if not left_points and not right_points:
            return _distance(items[left_id], items[right_id]) <= radii[left_id] + radii[right_id]
        if not left_points:
            left_points = (_machine_xy(items[left_id]),)
        if not right_points:
            right_points = (_machine_xy(items[right_id]),)
        best = min(
            hypot(lx - rx, ly - ry)
            for lx, ly in left_points
            for rx, ry in right_points
        )
        return best <= SOCKET_CONTACT_RADIUS_WORLD

    def adjacency_contact(left_id: int, right_id: int) -> bool:
        left_role = roles.get(left_id)
        right_role = roles.get(right_id)
        drive_roles = {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT}
        accessory_roles = {ROLE_HEAD, ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL}
        if left_role in drive_roles and right_role in drive_roles:
            return drive_contact(left_id, right_id)
        # Only powered accessories opt into the new visual connector authority.
        # Pipe/Fan pairs keep their dedicated endpoint mechanics below.
        if left_role in accessory_roles or right_role in accessory_roles:
            left_points = accessory_points.get(left_id)
            right_points = accessory_points.get(right_id)
            if left_points or right_points:
                if not left_points:
                    left_points = (_machine_xy(items[left_id]),)
                if not right_points:
                    right_points = (_machine_xy(items[right_id]),)
                best = min(
                    hypot(lx - rx, ly - ry)
                    for lx, ly in left_points
                    for rx, ry in right_points
                )
                return best <= ACCESSORY_SOCKET_CONTACT_RADIUS_WORLD
        return _distance(items[left_id], items[right_id]) <= radii[left_id] + radii[right_id]

    adjacency: dict[int, set[int]] = {instance_id: set() for instance_id in items}
    ids = sorted(items)
    for index, left_id in enumerate(ids):
        left = items[left_id]
        if roles[left_id] in {ROLE_FRAME, ROLE_COSMETIC}:
            continue
        for right_id in ids[index + 1:]:
            right = items[right_id]
            if roles[right_id] in {ROLE_FRAME, ROLE_COSMETIC}:
                continue
            if _machine_scope(left) != _machine_scope(right):
                continue
            if adjacency_contact(left_id, right_id):
                adjacency[left_id].add(right_id)
                adjacency[right_id].add(left_id)

    state: dict[int, dict[str, object]] = {
        instance_id: {
            "role": roles[instance_id],
            "powered": False,
            "core_id": None,
            "gear_id": None,
            "pivot_id": None,
            "parent_id": None,
            "local_dx": 0.0,
            "local_dy": 0.0,
            "anchor_end": None,
            "pipe_end": None,
            "attachment": None,
        }
        for instance_id in ids
    }

    # Validate a three-way drive triangle. If several valid drives overlap, the
    # stable lowest-id core/gear pair wins so replay/save behavior is deterministic.
    for pivot_id in ids:
        if roles[pivot_id] != ROLE_PIVOT:
            continue
        touching_cores = sorted(i for i in adjacency[pivot_id] if roles.get(i) == ROLE_CORE)
        touching_gears = sorted(i for i in adjacency[pivot_id] if roles.get(i) == ROLE_GEAR)
        chosen: tuple[int, int] | None = None
        for core_id in touching_cores:
            for gear_id in touching_gears:
                if gear_id in adjacency.get(core_id, set()):
                    chosen = (core_id, gear_id)
                    break
            if chosen is not None:
                break
        if chosen is None:
            continue
        core_id, gear_id = chosen
        state[pivot_id].update({"powered": True, "core_id": core_id, "gear_id": gear_id})
        # A valid drive makes the participating core and gear visibly active too.
        state[core_id]["powered"] = True
        state[gear_id].update({"powered": True, "core_id": core_id, "pivot_id": pivot_id})

    powered_pivots = [i for i in ids if roles[i] == ROLE_PIVOT and bool(state[i]["powered"])]

    # Pass 119: Pipe mechanics and Pipe power are separate. A saved hinge remains
    # mechanically valid even if the drive later loses power. For power flow, the
    # saved hinge must point at a currently powered Pivot in the same era/layer.
    # A Pipe with no hinge may create one only when an authored endpoint truly
    # touches the driven Gear/Pivot surface.
    powered_pipes: list[int] = []
    for instance_id in ids:
        if roles[instance_id] != ROLE_PIPE:
            continue

        saved_hinge_raw = items[instance_id].get("pipe_hinge_id", None)
        try:
            saved_hinge_id = int(saved_hinge_raw) if saved_hinge_raw is not None else None
        except (TypeError, ValueError, OverflowError):
            saved_hinge_id = None
        if (
            saved_hinge_id is not None
            and saved_hinge_id in items
            and roles.get(saved_hinge_id) == ROLE_PIVOT
            and _machine_scope(items[instance_id]) == _machine_scope(items[saved_hinge_id])
        ):
            state[instance_id].update({
                "pivot_id": saved_hinge_id,
                "parent_id": saved_hinge_id,
                "local_dx": float(items[instance_id].get("attach_local_dx", 0.0)),
                "local_dy": float(items[instance_id].get("attach_local_dy", 0.0)),
                "anchor_end": normalize_pipe_end(items[instance_id].get("pipe_anchor_end")),
                "attachment": "pivot_hinge",
            })
            if bool(state[saved_hinge_id]["powered"]):
                state[instance_id].update({
                    "powered": True,
                    "core_id": state[saved_hinge_id]["core_id"],
                    "gear_id": state[saved_hinge_id]["gear_id"],
                })
                powered_pipes.append(instance_id)
            continue

        ix, iy = _machine_xy(items[instance_id])
        pipe_angle = _machine_angle(items[instance_id])
        authored_endpoints = pipe_endpoints(
            ix, iy, pipe_angle, PIPE_ENDPOINT_OFFSET_WORLD * 2.0
        )
        pipe_candidates: list[tuple[float, int, float, float, str]] = []
        for pivot_id in powered_pivots:
            if _machine_scope(items[instance_id]) != _machine_scope(items[pivot_id]):
                continue
            gear_id = state[pivot_id].get("gear_id")
            try:
                gear_id_int = int(gear_id) if gear_id is not None else None
            except (TypeError, ValueError, OverflowError):
                gear_id_int = None
            effective_parent = items.get(gear_id_int) if gear_id_int is not None else items[pivot_id]
            px, py = _machine_xy(effective_parent)
            drive_radius = radii.get(gear_id_int, radii[pivot_id]) if gear_id_int is not None else radii[pivot_id]
            contact_limit = max(1.0, float(drive_radius)) + PIPE_GEAR_CONTACT_SLOP_WORLD
            for endpoint_name in (PIPE_END_LEFT, PIPE_END_RIGHT):
                ex, ey = authored_endpoints[endpoint_name]
                endpoint_distance = hypot(ex - px, ey - py)
                if endpoint_distance <= contact_limit:
                    pipe_candidates.append((endpoint_distance, pivot_id, px, py, endpoint_name))
        if not pipe_candidates:
            continue
        _, pivot_id, px, py, contact_end = min(
            pipe_candidates, key=lambda entry: (entry[0], entry[1], entry[4])
        )
        anchor_x, anchor_y = authored_endpoints[contact_end]
        state[instance_id].update({
            "powered": True,
            "pivot_id": pivot_id,
            "parent_id": pivot_id,
            "core_id": state[pivot_id]["core_id"],
            "gear_id": state[pivot_id]["gear_id"],
            "local_dx": anchor_x - px,
            "local_dy": anchor_y - py,
            "anchor_end": contact_end,
            "attachment": "pivot_hinge",
        })
        powered_pipes.append(instance_id)

    # Fans may attach to the end of a powered pipe. Because the pipe itself does
    # not rotate while orbiting, the fan inherits the pipe's translation while
    # retaining its own local offset and its own in-place spin.
    for instance_id in ids:
        if roles[instance_id] != ROLE_FAN:
            continue
        fan_x, fan_y = _machine_xy(items[instance_id])
        pipe_candidates: list[tuple[float, int]] = []
        for pipe_id in powered_pipes:
            if _machine_scope(items[instance_id]) != _machine_scope(items[pipe_id]):
                continue
            pipe_x, pipe_y = _machine_xy(items[pipe_id])
            pipe_angle = _machine_angle(items[pipe_id])
            pipe_radians = radians(pipe_angle)
            ex = cos(pipe_radians) * PIPE_ENDPOINT_OFFSET_WORLD
            ey = -sin(pipe_radians) * PIPE_ENDPOINT_OFFSET_WORLD
            for pipe_end, (endpoint_x, endpoint_y) in (
                (PIPE_END_LEFT, (pipe_x - ex, pipe_y - ey)),
                (PIPE_END_RIGHT, (pipe_x + ex, pipe_y + ey)),
            ):
                endpoint_distance = hypot(fan_x - endpoint_x, fan_y - endpoint_y)
                if endpoint_distance <= PIPE_ENDPOINT_ATTACH_RADIUS_WORLD:
                    pipe_candidates.append((endpoint_distance, pipe_id, pipe_end))
        if pipe_candidates:
            _, pipe_id, pipe_end = min(pipe_candidates, key=lambda entry: (entry[0], entry[1], entry[2]))
            pipe_x, pipe_y = _machine_xy(items[pipe_id])
            pivot_id = int(state[pipe_id]["pivot_id"])
            state[instance_id].update({
                "powered": True,
                "pivot_id": pivot_id,
                "parent_id": pipe_id,
                "core_id": state[pipe_id]["core_id"],
                "gear_id": state[pipe_id]["gear_id"],
                "local_dx": fan_x - pipe_x,
                "local_dy": fan_y - pipe_y,
                "pipe_end": pipe_end,
                "attachment": "pipe_child_spin",
            })
            continue
        pivot_candidates: list[tuple[float, int]] = []
        for pivot_id in powered_pivots:
            if _machine_scope(items[instance_id]) != _machine_scope(items[pivot_id]):
                continue
            gear_id = state[pivot_id].get("gear_id")
            try:
                effective_parent = items.get(int(gear_id)) if gear_id is not None else items[pivot_id]
            except (TypeError, ValueError, OverflowError):
                effective_parent = items[pivot_id]
            px, py = _machine_xy(effective_parent)
            distance = hypot(fan_x - px, fan_y - py)
            if distance <= radii[instance_id] + radii[pivot_id]:
                pivot_candidates.append((distance, pivot_id))
        if not pivot_candidates:
            continue
        _, pivot_id = min(pivot_candidates, key=lambda entry: (entry[0], entry[1]))
        state[instance_id].update({
            "powered": True,
            "pivot_id": pivot_id,
            "parent_id": pivot_id,
            "core_id": state[pivot_id]["core_id"],
            "gear_id": state[pivot_id]["gear_id"],
            "attachment": "spin_in_place",
        })

    # Pass 141: control heads, actuators, sensors and tools are powered
    # accessories.  They may consume a nearby powered drive/output, but they do
    # not transmit power onward and therefore cannot accidentally become a new
    # shortcut around the Core + Gear + Pivot authority.
    accessory_roles = {ROLE_HEAD, ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL}
    powered_sources = {
        instance_id
        for instance_id in ids
        if bool(state[instance_id]["powered"])
        and roles[instance_id] in {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT, ROLE_PIPE, ROLE_FAN}
    }
    for accessory_id in ids:
        if roles[accessory_id] not in accessory_roles:
            continue
        candidates = [
            source_id
            for source_id in adjacency.get(accessory_id, set())
            if source_id in powered_sources
            and _machine_scope(items[accessory_id]) == _machine_scope(items[source_id])
        ]
        if not candidates:
            continue
        parent_id = min(candidates, key=lambda pid: (_distance(items[accessory_id], items[pid]), pid))
        state[accessory_id].update({
            "powered": True,
            "parent_id": parent_id,
            "core_id": state[parent_id].get("core_id") if state[parent_id].get("core_id") is not None else (parent_id if roles[parent_id] == ROLE_CORE else None),
            "gear_id": state[parent_id].get("gear_id") if state[parent_id].get("gear_id") is not None else (parent_id if roles[parent_id] == ROLE_GEAR else None),
            "pivot_id": state[parent_id].get("pivot_id") if state[parent_id].get("pivot_id") is not None else (parent_id if roles[parent_id] == ROLE_PIVOT else None),
            "attachment": "powered_accessory",
        })

    # Frame plates remain cosmetic and never transmit power, but a plate touching
    # any powered core/gear/pivot gets a presentation-only ticking flag.
    powered_drive_ids = {i for i in ids if bool(state[i]["powered"]) and roles[i] in {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT}}
    for frame_id in ids:
        if roles[frame_id] != ROLE_FRAME:
            continue
        candidates = []
        for powered_id in powered_drive_ids:
            if _machine_scope(items[frame_id]) != _machine_scope(items[powered_id]):
                continue
            if _distance(items[frame_id], items[powered_id]) <= radii[frame_id] + radii[powered_id]:
                candidates.append(powered_id)
        if candidates:
            parent_id = min(candidates, key=lambda pid: (_distance(items[frame_id], items[pid]), pid))
            state[frame_id].update({"powered": True, "parent_id": parent_id, "attachment": "tick_overlay"})

    return state
