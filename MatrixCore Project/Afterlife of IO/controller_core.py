from __future__ import annotations

"""Controller/input helpers for Afterlife of IO.

This module intentionally has no pygame dependency so deadzone and contextual
button mapping rules can be tested without an SDL device.  The runtime bridge
in ``main.py`` translates these symbolic actions back into the established
keyboard/mouse authority.
"""

from dataclasses import dataclass
import math

DEFAULT_DEADZONE = 0.20
CURSOR_SPEED = 780.0


def radial_deadzone(x: float, y: float, deadzone: float = DEFAULT_DEADZONE) -> tuple[float, float]:
    """Apply a radial deadzone while preserving full-scale analog range."""
    try:
        x = float(x)
        y = float(y)
        deadzone = max(0.0, min(0.95, float(deadzone)))
    except (TypeError, ValueError):
        return 0.0, 0.0
    magnitude = math.hypot(x, y)
    if not math.isfinite(magnitude) or magnitude <= deadzone:
        return 0.0, 0.0
    if magnitude > 1.0:
        x /= magnitude
        y /= magnitude
        magnitude = 1.0
    scaled = (magnitude - deadzone) / max(1e-6, 1.0 - deadzone)
    factor = scaled / max(1e-6, magnitude)
    return x * factor, y * factor


@dataclass(frozen=True)
class ControllerContext:
    modal: bool = False
    machine_focus: bool = False
    projection_active: bool = False
    snap_edit: bool = False


def button_action(button: str, context: ControllerContext) -> str | None:
    """Return a semantic action for a standardized SDL/Xbox-style button name.

    The names describe positions, not hardware branding.  SDL's controller
    layer maps Xbox/PlayStation/Nintendo-style pads into the same A/B/X/Y,
    shoulder, stick-click and menu/back positions before this function runs.
    """
    button = str(button).strip().lower()
    if context.modal:
        modal_map = {
            "a": "confirm", "b": "back", "start": "back",
            "dpad_up": "ui_up", "dpad_down": "ui_down",
            "dpad_left": "ui_left", "dpad_right": "ui_right",
        }
        return modal_map.get(button)
    if button == "a":
        if context.machine_focus:
            return "confirm"
        return "interact"
    if button == "b":
        return "back"
    if button == "x":
        if context.machine_focus and not context.modal:
            return "machine_grab"
        return "hop"
    if button == "y":
        if context.machine_focus and not context.modal:
            return "machine_reclaim"
        return "projection"
    if button == "leftshoulder":
        return "veil_ward"
    if button == "rightshoulder":
        return "causal_resonance"
    if button == "back":
        return "archive"
    if button == "start":
        return "pause"
    if button == "leftstick":
        return "sprint_toggle"
    if button == "rightstick":
        if context.machine_focus and not context.modal:
            return "machine_flip"
        return "inventory"
    if button == "dpad_up":
        return "ui_up" if context.modal else "help"
    if button == "dpad_down":
        return "ui_down" if context.modal else "machine_focus"
    if button == "dpad_left":
        return "ui_left" if context.modal else "machine_prev"
    if button == "dpad_right":
        return "ui_right" if context.modal else "machine_next"
    return None


def controller_help_lines(machine_available: bool, powers: tuple[bool, bool], projection_available: bool) -> tuple[str, str]:
    """Compact controller help that fits the existing two-line F1 safe strip."""
    causal, ward = powers
    line1 = "LS move   •   LS click sprint toggle   •   X hop   •   A interact   •   VIEW archive"
    extras: list[str] = []
    if ward:
        extras.append("LB ward")
    if causal:
        extras.append("RB resonance")
    if projection_available:
        extras.append("Y drone")
    if machine_available:
        extras.append("D↓ machine focus")
    line2 = "   •   ".join(extras) if extras else "D↑ help   •   RS click inventory   •   MENU pause"
    if extras:
        line2 += "   •   D↑ help   •   RS click inventory   •   MENU pause"
    return line1, line2
