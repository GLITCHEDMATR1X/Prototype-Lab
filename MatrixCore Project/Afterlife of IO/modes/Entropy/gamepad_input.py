from __future__ import annotations

"""Small SDL game-controller abstraction for Entropy.

The gameplay code stays pygame-ce based today.  This module deliberately uses
SDL's controller mapping rather than raw joystick button numbers so Xbox,
PlayStation and other mapped pads expose one stable A/B/X/Y + stick layout.
The eventual GDK port can swap this provider for GameInput without rewriting
mission/gameplay code.
"""

from dataclasses import dataclass
import math
import time
from typing import Dict, Optional, Tuple

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except Exception:  # pygame build without the experimental SDL controller wrapper
    sdl_controller = None

_ACTIVE_GAMEPAD = None


def set_active_gamepad(gamepad) -> None:
    global _ACTIVE_GAMEPAD
    _ACTIVE_GAMEPAD = gamepad


def get_active_gamepad():
    return _ACTIVE_GAMEPAD


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _deadzone_axis(value: float, deadzone: float) -> float:
    value = _clamp(value)
    mag = abs(value)
    if mag <= deadzone:
        return 0.0
    scaled = (mag - deadzone) / max(1e-6, 1.0 - deadzone)
    return math.copysign(min(1.0, scaled), value)


@dataclass(frozen=True)
class GamepadFrame:
    move_x: float = 0.0
    move_y: float = 0.0
    look_x: float = 0.0
    look_y: float = 0.0
    trigger_left: float = 0.0
    trigger_right: float = 0.0


class ControllerInput:
    """One-primary-controller input with hot-plug and edge detection."""

    BUTTON_NAMES = (
        "a", "b", "x", "y", "dpad_up", "dpad_down", "dpad_left", "dpad_right",
        "left_shoulder", "right_shoulder", "left_stick", "right_stick", "view", "start",
    )

    _BUTTON_CONSTANTS = {
        "a": "CONTROLLER_BUTTON_A",
        "b": "CONTROLLER_BUTTON_B",
        "x": "CONTROLLER_BUTTON_X",
        "y": "CONTROLLER_BUTTON_Y",
        "dpad_up": "CONTROLLER_BUTTON_DPAD_UP",
        "dpad_down": "CONTROLLER_BUTTON_DPAD_DOWN",
        "dpad_left": "CONTROLLER_BUTTON_DPAD_LEFT",
        "dpad_right": "CONTROLLER_BUTTON_DPAD_RIGHT",
        "left_shoulder": "CONTROLLER_BUTTON_LEFTSHOULDER",
        "right_shoulder": "CONTROLLER_BUTTON_RIGHTSHOULDER",
        "left_stick": "CONTROLLER_BUTTON_LEFTSTICK",
        "right_stick": "CONTROLLER_BUTTON_RIGHTSTICK",
        "view": "CONTROLLER_BUTTON_BACK",
        "start": "CONTROLLER_BUTTON_START",
    }

    _AXIS_CONSTANTS = {
        "left_x": "CONTROLLER_AXIS_LEFTX",
        "left_y": "CONTROLLER_AXIS_LEFTY",
        "right_x": "CONTROLLER_AXIS_RIGHTX",
        "right_y": "CONTROLLER_AXIS_RIGHTY",
        "trigger_left": "CONTROLLER_AXIS_TRIGGERLEFT",
        "trigger_right": "CONTROLLER_AXIS_TRIGGERRIGHT",
    }

    def __init__(self, deadzone: float = 0.19, nav_threshold: float = 0.62) -> None:
        self.deadzone = max(0.05, min(0.45, float(deadzone)))
        self.nav_threshold = max(self.deadzone + 0.10, min(0.90, float(nav_threshold)))
        self.controller = None
        self.controller_name = ""
        self.connected = False
        self.just_connected = False
        self.just_disconnected = False
        self.frame = GamepadFrame()
        self._buttons: Dict[str, bool] = {name: False for name in self.BUTTON_NAMES}
        self._previous_buttons: Dict[str, bool] = dict(self._buttons)
        self._pressed: Dict[str, bool] = dict(self._buttons)
        self._previous_nav = {name: False for name in ("up", "down", "left", "right")}
        self._nav_pressed = dict(self._previous_nav)
        self._last_scan = 0.0
        self._rescan_requested = False
        self.last_input_source = "keyboard"
        self._enabled = sdl_controller is not None
        if self._enabled:
            try:
                sdl_controller.init()
            except Exception:
                self._enabled = False
            if self._enabled:
                try:
                    sdl_controller.set_eventstate(True)
                except Exception:
                    # Event notifications are an optimization only; the polling
                    # rescan below remains the hot-plug fallback.
                    pass
        self.rescan(force=True)
        set_active_gamepad(self)

    def close(self) -> None:
        try:
            if self.controller is not None:
                self.controller.quit()
        except Exception:
            pass
        self.controller = None
        self.connected = False
        set_active_gamepad(None)

    def mark_keyboard_mouse(self) -> None:
        self.last_input_source = "keyboard"

    def _controller_attached(self) -> bool:
        try:
            return bool(self.controller is not None and self.controller.attached())
        except Exception:
            return False

    def rescan(self, force: bool = False) -> bool:
        if not self._enabled:
            return False
        now = time.monotonic()
        if not force and now - self._last_scan < 0.8:
            return self.connected
        self._last_scan = now

        if self._controller_attached():
            self.connected = True
            return True

        was_connected = bool(self.connected)
        try:
            if self.controller is not None:
                self.controller.quit()
        except Exception:
            pass
        self.controller = None
        self.controller_name = ""
        self.connected = False

        try:
            count = int(sdl_controller.get_count())
        except Exception:
            count = 0
        for index in range(max(0, count)):
            try:
                if not sdl_controller.is_controller(index):
                    continue
                candidate = sdl_controller.Controller(index)
                self.controller = candidate
                name_lookup = getattr(sdl_controller, "name_forindex", None)
                if callable(name_lookup):
                    try:
                        self.controller_name = str(name_lookup(index) or "Game Controller")
                    except Exception:
                        self.controller_name = "Game Controller"
                else:
                    self.controller_name = "Game Controller"
                self.connected = bool(candidate.attached())
                if self.connected:
                    break
            except Exception:
                self.controller = None
                self.connected = False

        self.just_connected = self.connected and not was_connected
        self.just_disconnected = was_connected and not self.connected
        return self.connected

    def handle_event(self, event) -> None:
        """React to SDL hot-plug notifications without consuming gameplay events."""
        if not self._enabled:
            return
        event_type = getattr(event, "type", None)
        added = getattr(pygame, "CONTROLLERDEVICEADDED", None)
        removed = getattr(pygame, "CONTROLLERDEVICEREMOVED", None)
        remapped = getattr(pygame, "CONTROLLERDEVICEREMAPPED", None)
        if event_type in tuple(v for v in (added, removed, remapped) if v is not None):
            # Defer the actual rescan until update(). That keeps just_connected /
            # just_disconnected alive for the main loop instead of setting the
            # edge after input processing and then clearing it next frame.
            self._rescan_requested = True

    def _button(self, name: str) -> bool:
        if not self.connected or self.controller is None or sdl_controller is None:
            return False
        const_name = self._BUTTON_CONSTANTS[name]
        const = getattr(sdl_controller, const_name, None)
        if const is None:
            return False
        try:
            return bool(self.controller.get_button(const))
        except Exception:
            return False

    def _axis_raw(self, name: str) -> float:
        if not self.connected or self.controller is None or sdl_controller is None:
            return 0.0
        const_name = self._AXIS_CONSTANTS[name]
        const = getattr(sdl_controller, const_name, None)
        if const is None:
            return 0.0
        try:
            raw = float(self.controller.get_axis(const))
        except Exception:
            return 0.0
        if name.startswith("trigger"):
            return max(0.0, min(1.0, raw / 32768.0))
        return _clamp(raw / 32767.0)

    def update(self) -> GamepadFrame:
        self.just_connected = False
        self.just_disconnected = False
        requested = bool(self._rescan_requested)
        self._rescan_requested = False
        attached = self._controller_attached()
        if requested or not attached:
            # If a previously active controller disappeared, bypass the normal
            # idle scan throttle so a 60-second expedition pauses immediately.
            self.rescan(force=requested or bool(self.connected))
        if not self.connected:
            self.frame = GamepadFrame()
            self._previous_buttons = dict(self._buttons)
            self._buttons = {name: False for name in self.BUTTON_NAMES}
            self._pressed = {name: False for name in self.BUTTON_NAMES}
            self._nav_pressed = {name: False for name in self._nav_pressed}
            return self.frame

        lx = _deadzone_axis(self._axis_raw("left_x"), self.deadzone)
        ly = _deadzone_axis(self._axis_raw("left_y"), self.deadzone)
        rx = _deadzone_axis(self._axis_raw("right_x"), self.deadzone)
        ry = _deadzone_axis(self._axis_raw("right_y"), self.deadzone)
        lt = self._axis_raw("trigger_left")
        rt = self._axis_raw("trigger_right")

        previous = dict(self._buttons)
        current = {name: self._button(name) for name in self.BUTTON_NAMES}
        self._previous_buttons = previous
        self._buttons = current
        self._pressed = {name: current[name] and not previous.get(name, False) for name in self.BUTTON_NAMES}

        nav = {
            "up": current["dpad_up"] or ly <= -self.nav_threshold,
            "down": current["dpad_down"] or ly >= self.nav_threshold,
            "left": current["dpad_left"] or lx <= -self.nav_threshold,
            "right": current["dpad_right"] or lx >= self.nav_threshold,
        }
        self._nav_pressed = {name: nav[name] and not self._previous_nav.get(name, False) for name in nav}
        self._previous_nav = nav

        if current["dpad_left"] and abs(lx) < self.deadzone:
            lx = -1.0
        elif current["dpad_right"] and abs(lx) < self.deadzone:
            lx = 1.0
        if current["dpad_up"] and abs(ly) < self.deadzone:
            ly = -1.0
        elif current["dpad_down"] and abs(ly) < self.deadzone:
            ly = 1.0

        self.frame = GamepadFrame(lx, ly, rx, ry, lt, rt)
        meaningful_axis = max(abs(lx), abs(ly), abs(rx), abs(ry), lt, rt) > 0.28
        if any(self._pressed.values()) or meaningful_axis:
            self.last_input_source = "controller"
        return self.frame

    def held(self, name: str) -> bool:
        return bool(self._buttons.get(name, False))

    def pressed(self, name: str) -> bool:
        return bool(self._pressed.get(name, False))

    def nav_pressed(self, direction: str) -> bool:
        return bool(self._nav_pressed.get(direction, False))

    def move_vector(self) -> Tuple[float, float]:
        return (self.frame.move_x, self.frame.move_y)

    def look_vector(self) -> Tuple[float, float]:
        return (self.frame.look_x, self.frame.look_y)

    def rumble(self, low: float = 0.25, high: float = 0.45, duration_ms: int = 120) -> bool:
        if not self.connected or self.controller is None:
            return False
        try:
            return bool(self.controller.rumble(max(0.0, min(1.0, low)), max(0.0, min(1.0, high)), max(0, int(duration_ms))))
        except Exception:
            return False
