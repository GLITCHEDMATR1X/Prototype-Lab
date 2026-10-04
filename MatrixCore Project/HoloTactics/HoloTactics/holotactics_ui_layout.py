from __future__ import annotations

# aspect2d is 16:9 by default in this build: x approximately [-1.777, 1.777], y [-1.0, 1.0].
# Pass 30 redo: every panel snaps to a shared outer margin and uses a consistent
# internal padding model. The tactical board owns the center; HUD owns the edges.
ASPECT_X = 16.0 / 9.0
SAFE_MARGIN = 0.012
MIN_PANEL_GAP = 0.035

OUTER_LEFT = -1.72
OUTER_RIGHT = 1.72
LEFT_INNER = -1.06
RIGHT_INNER = 1.06

UI_FRAMES: dict[str, tuple[float, float, float, float]] = {
    "ui_title_glass": (-0.54, 0.54, 0.900, 0.985),
    "ui_squad_glass": (OUTER_LEFT, LEFT_INNER, 0.555, 0.920),
    "ui_mission_glass": (RIGHT_INNER, OUTER_RIGHT, 0.500, 0.920),
    "ui_comms_glass": (RIGHT_INNER, OUTER_RIGHT, -0.940, -0.650),
    "ui_help_glass": (OUTER_LEFT, -0.45, -0.940, -0.790),
}

# All body panels use 0.06 horizontal inset and approximately 0.06 top inset.
UI_TEXT_POS: dict[str, tuple[float, float]] = {
    "title": (0.0, 0.952),
    "subtitle": (0.0, 0.915),
    "squad": (OUTER_LEFT + 0.06, 0.855),
    "mission": (RIGHT_INNER + 0.06, 0.855),
    "comms": (RIGHT_INNER + 0.06, -0.710),
    "help": (OUTER_LEFT + 0.06, -0.835),
    "result": (0.0, 0.05),
    "menu": (OUTER_RIGHT - 0.06, -0.705),
}

UI_TEXT_SCALE: dict[str, float] = {
    "title": 0.042,
    "subtitle": 0.020,
    "squad": 0.040,
    "mission": 0.037,
    "comms": 0.035,
    "help": 0.033,
    "result": 0.072,
    "menu": 0.030,
}


def rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float], gap: float = 0.0) -> bool:
    al, ar, ab, at = a
    bl, br, bb, bt = b
    return not (ar + gap <= bl or br + gap <= al or at + gap <= bb or bt + gap <= ab)


def validate_ui_layout() -> list[str]:
    issues: list[str] = []
    for name, (left, right, bottom, top) in UI_FRAMES.items():
        if left >= right or bottom >= top:
            issues.append(f"{name}: invalid frame ordering")
        if left < -ASPECT_X + SAFE_MARGIN or right > ASPECT_X - SAFE_MARGIN:
            issues.append(f"{name}: outside horizontal safe area")
        if bottom < -1.0 + SAFE_MARGIN or top > 1.0 - SAFE_MARGIN:
            issues.append(f"{name}: outside vertical safe area")
    names = list(UI_FRAMES)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if rects_overlap(UI_FRAMES[a], UI_FRAMES[b], MIN_PANEL_GAP):
                issues.append(f"{a} overlaps {b}")

    # Alignment contracts: left-column panels share an outer edge; right-column
    # panels share both edges. These catch visual drift that overlap tests miss.
    if abs(UI_FRAMES["ui_squad_glass"][0] - UI_FRAMES["ui_help_glass"][0]) > 1e-6:
        issues.append("left column outer edges are not aligned")
    if abs(UI_FRAMES["ui_mission_glass"][0] - UI_FRAMES["ui_comms_glass"][0]) > 1e-6:
        issues.append("right column inner edges are not aligned")
    if abs(UI_FRAMES["ui_mission_glass"][1] - UI_FRAMES["ui_comms_glass"][1]) > 1e-6:
        issues.append("right column outer edges are not aligned")
    return issues
