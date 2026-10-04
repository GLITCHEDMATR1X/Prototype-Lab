from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
checks: list[dict] = []


def require(condition: bool, label: str, detail: str = "") -> None:
    ok = bool(condition)
    checks.append({"label": label, "pass": ok, "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}: {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise AssertionError(label)


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _fake_gamepad_module():
    pygame = types.ModuleType("pygame")
    pygame.CONTROLLERDEVICEADDED = 0x650
    pygame.CONTROLLERDEVICEREMOVED = 0x651
    pygame.CONTROLLERDEVICEREMAPPED = 0x652

    sdl2 = types.ModuleType("pygame._sdl2")
    controller = types.ModuleType("pygame._sdl2.controller")

    button_names = [
        "A", "B", "X", "Y", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
        "LEFTSHOULDER", "RIGHTSHOULDER", "LEFTSTICK", "RIGHTSTICK", "BACK", "START",
    ]
    axis_names = ["LEFTX", "LEFTY", "RIGHTX", "RIGHTY", "TRIGGERLEFT", "TRIGGERRIGHT"]
    for i, name in enumerate(button_names):
        setattr(controller, f"CONTROLLER_BUTTON_{name}", i)
    for i, name in enumerate(axis_names):
        setattr(controller, f"CONTROLLER_AXIS_{name}", i)

    state = {
        "count": 1,
        "attached": True,
        "buttons": {},
        "axes": {},
        "rumble": [],
        "eventstate": None,
    }

    class FakeController:
        def __init__(self, index):
            self.index = index
        def attached(self):
            return bool(state["attached"])
        def quit(self):
            pass
        def get_button(self, const):
            return int(bool(state["buttons"].get(const, False)))
        def get_axis(self, const):
            return int(state["axes"].get(const, 0))
        def rumble(self, low, high, duration):
            state["rumble"].append((low, high, duration))
            return True

    controller.init = lambda: None
    controller.set_eventstate = lambda value: state.__setitem__("eventstate", value)
    controller.get_count = lambda: int(state["count"])
    controller.is_controller = lambda index: 0 <= index < int(state["count"])
    controller.Controller = FakeController
    controller.name_forindex = lambda index: "Synthetic Xbox Controller"
    sdl2.controller = controller
    pygame._sdl2 = sdl2
    return pygame, sdl2, controller, state


def run_provider_checks() -> None:
    saved = {k: sys.modules.get(k) for k in ("pygame", "pygame._sdl2", "pygame._sdl2.controller")}
    pygame, sdl2, ctrl, state = _fake_gamepad_module()
    sys.modules["pygame"] = pygame
    sys.modules["pygame._sdl2"] = sdl2
    sys.modules["pygame._sdl2.controller"] = ctrl
    try:
        spec = importlib.util.spec_from_file_location("pass29_gamepad_test", ROOT / "gamepad_input.py")
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        pad = module.ControllerInput(deadzone=0.19, nav_threshold=0.62)
        require(pad.connected, "synthetic mapped controller attaches")
        require("Xbox" in pad.controller_name, "mapped controller exposes friendly device name")
        require(state["eventstate"] is True, "SDL controller hot-plug events enabled")

        # Deadzone remains neutral.
        state["axes"][ctrl.CONTROLLER_AXIS_LEFTX] = 3000
        pad.update()
        require(abs(pad.move_vector()[0]) < 1e-6, "left-stick deadzone suppresses drift")

        # Analog motion and trigger normalization.
        state["axes"][ctrl.CONTROLLER_AXIS_LEFTX] = 24000
        state["axes"][ctrl.CONTROLLER_AXIS_LEFTY] = -21000
        state["axes"][ctrl.CONTROLLER_AXIS_RIGHTX] = 18000
        state["axes"][ctrl.CONTROLLER_AXIS_TRIGGERLEFT] = 16384
        state["axes"][ctrl.CONTROLLER_AXIS_TRIGGERRIGHT] = 30000
        frame = pad.update()
        require(frame.move_x > 0.5 and frame.move_y < -0.45, "left stick provides normalized analog movement")
        require(frame.look_x > 0.35, "right stick provides normalized look input")
        require(0.45 <= frame.trigger_left <= 0.55 and frame.trigger_right > 0.85, "triggers normalize to 0..1")

        # A is edge-triggered exactly once while held.
        state["buttons"][ctrl.CONTROLLER_BUTTON_A] = True
        pad.update()
        require(pad.pressed("a") and pad.held("a"), "A press produces one action edge")
        pad.update()
        require(not pad.pressed("a") and pad.held("a"), "held A does not repeat one-shot action")
        state["buttons"][ctrl.CONTROLLER_BUTTON_A] = False
        pad.update()

        # Digital navigation is edge-triggered and D-pad can produce movement.
        state["axes"][ctrl.CONTROLLER_AXIS_LEFTX] = 0
        state["axes"][ctrl.CONTROLLER_AXIS_LEFTY] = 0
        state["buttons"][ctrl.CONTROLLER_BUTTON_DPAD_DOWN] = True
        frame = pad.update()
        require(pad.nav_pressed("down"), "D-pad navigation produces one focus edge")
        require(frame.move_y == 1.0, "D-pad remains a digital movement fallback")
        pad.update()
        require(not pad.nav_pressed("down"), "held D-pad does not race through menu focus")
        state["buttons"][ctrl.CONTROLLER_BUTTON_DPAD_DOWN] = False
        pad.update()

        # Disconnect neutralizes input, then a rescan can reconnect.
        state["attached"] = False
        state["count"] = 0
        pad._last_scan = 0.0
        pad.update()
        require(not pad.connected and pad.just_disconnected, "controller disconnect is detected")
        require(pad.move_vector() == (0.0, 0.0), "disconnect returns neutral gameplay input")
        state["attached"] = True
        state["count"] = 1
        pad._last_scan = 0.0
        pad.rescan(force=True)
        require(pad.connected and pad.just_connected, "controller reconnect is detected")

        # SDL remove event is deferred to update so the disconnect edge cannot
        # be cleared before the app sees it on the following frame.
        state["attached"] = False
        state["count"] = 0
        pad.handle_event(types.SimpleNamespace(type=pygame.CONTROLLERDEVICEREMOVED))
        pad.update()
        require(not pad.connected and pad.just_disconnected, "SDL remove event survives into the app-facing update edge")

        pad.close()
        require(module.get_active_gamepad() is None, "controller provider releases global active pad on shutdown")
    finally:
        sys.modules.pop("pass29_gamepad_test", None)
        for key, old in saved.items():
            if old is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = old


def main() -> int:
    core = _text("space_core.py")
    gamepad = _text("gamepad_input.py")
    ui = _text("standard_ui.py")
    terrains = _text("terrains.py")
    interiors = _text("interiors.py")
    manifest = json.loads(_text("build_manifest.json"))

    for name in ("space_core.py", "gamepad_input.py", "standard_ui.py", "terrains.py", "interiors.py"):
        ast.parse(_text(name), filename=name)
    require(True, "controller-facing runtime modules parse")

    # SDL's mapped controller layer; reject the brittle raw joystick-index pattern.
    require("pygame._sdl2" in gamepad and "CONTROLLER_BUTTON_A" in gamepad and "CONTROLLER_AXIS_LEFTX" in gamepad,
            "standardized SDL controller mapping is used")
    require("get_button(0)" not in gamepad and "get_axis(0)" not in gamepad,
            "no hard-coded raw gamepad button/axis indices")
    require("deadzone" in gamepad and "nav_threshold" in gamepad, "analog deadzone and menu threshold are explicit")
    require("just_connected" in gamepad and "just_disconnected" in gamepad, "controller hot-plug state is tracked")

    # Full expedition contexts.
    require("get_active_gamepad" in terrains and "move_vector" in terrains, "surface traversal accepts controller movement")
    require("get_active_gamepad" in interiors and "move_vector" in interiors, "ship interior accepts controller movement")
    for token in ("thrust_axis", "strafe_axis", "vertical_axis", "roll_axis"):
        require(token in core, f"flight analog channel wired: {token}")
    require('gamepad.held("a")' in core and 'gamepad.held("b")' in core, "flight boost and brake support held controller input")
    require("look_vector" in core and "right stick" in ui.lower(), "right-stick flight look is routed and documented")

    # Controller-first UI has focus navigation rather than a virtual mouse.
    require("pause_selection" in core and "settings_selection" in core, "pause/settings retain explicit focus state")
    require('gamepad.nav_pressed("up")' in core and 'gamepad.nav_pressed("down")' in core,
            "D-pad/left-stick menu focus navigation wired")
    require('gamepad.pressed("a")' in core and 'gamepad.pressed("b")' in core, "A confirm / B back contract wired")
    require("controller_controls" in ui and "DPAD / LEFT STICK SELECT" in ui, "controller-specific help and pause prompts exist")
    require('if controls_visible and gamepad.pressed("view"):' in core and 'K_F1' in core,
            "VIEW closes a gameplay controls panel before opening mission brief")
    require("draw_settings_menu" in ui and "LEFT / RIGHT ADJUST" in ui, "settings are controller-adjustable")
    require("pygame.mouse.set_pos" not in gamepad and "MOUSEMOTION" not in gamepad,
            "controller UI does not emulate a mouse cursor")

    # Timed-game safety on focus/controller loss.
    require("CONTROLLER DISCONNECTED" in core and "set_paused(True)" in core, "disconnect pauses the expedition safely")
    require("WINDOW FOCUS LOST" in core and "pygame.display.get_active" in core, "focus loss pauses the expedition safely")
    require("collapse_frozen = paused" in core, "paused/controller-loss state freezes collapse lifetime")
    require("gamepad.handle_event(e)" in core, "controller add/remove/remap events reach provider")
    require("gamepad.close()" in core, "controller provider is closed on clean shutdown")

    # Cleanup: fragment recovery is risk/reward, never a hidden forced warp.
    stale = ("AUTO_OBJECTIVE_WARP", "objective_warp_queued", "queue_objective_autowarp", "commit_objective_autowarp")
    for token in stale:
        require(token not in core, f"stale objective auto-warp removed: {token}")
    require("Data Fragment recovery never auto-warps" in core, "explicit player-owned departure contract documented in runtime")

    # Manifest must identify this pass and the controller provider.
    require(int(manifest.get("pass", 0)) == 30, "manifest identifies Pass 30")
    require("gamepad_input.py" in manifest.get("active_modules", []), "controller provider is an active runtime module")
    require(bool(manifest.get("controller_contract")), "manifest records controller contract")

    run_provider_checks()

    report = {
        "pass": 30,
        "title": "Controller Regression / Save-Crash Hardening",
        "checks": len(checks),
        "passed": sum(1 for c in checks if c["pass"]),
        "failed": [c for c in checks if not c["pass"]],
        "result": "PASS" if all(c["pass"] for c in checks) else "FAIL",
    }
    out = ROOT / "Entropy_Pass30_controller_regression.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CHECKS={report['passed']}/{report['checks']}")
    print(f"FINAL_RESULT={report['result']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
