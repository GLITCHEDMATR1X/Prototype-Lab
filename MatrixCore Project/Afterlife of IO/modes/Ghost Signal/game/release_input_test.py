from __future__ import annotations

import json
from pathlib import Path

import pygame

from game.app import AppConfig, GhostSignalApp
from game.results import result_dir
from game.states import GameState
from game.version import BUILD_LABEL, PROJECT_NAME, VERSION


def run_release_input_test() -> int:
    checks: list[dict[str, object]] = []

    def record(name: str, passed: object, detail: object = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    app = GhostSignalApp(AppConfig(no_audio=True, quick_test=True, max_frames=1, window_size=(1280, 720)))
    try:
        record("initial_title_state", app.state is GameState.TITLE, app.state.value)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1, mod=0))
        app._events()
        record("f1_opens_help", app.show_help is True)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        app._events()
        record("escape_closes_help", app.show_help is False and app.state is GameState.TITLE)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2, mod=0))
        app._events()
        record("f2_opens_settings", app.show_settings is True)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        app._events()
        record("escape_closes_settings", app.show_settings is False)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
        app._events()
        record("enter_starts_campaign", app.state is GameState.CITY_MAP, app.state.value)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        app._events()
        record("escape_opens_pause", app.state is GameState.PAUSED, app.state.value)

        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        app._events()
        record("escape_resumes", app.state is GameState.CITY_MAP, app.state.value)

        start_fullscreen = app.fullscreen
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, mod=0))
        app._events()
        record("f11_enters_fullscreen", app.fullscreen is not start_fullscreen and pygame.display.get_surface() is not None, app.fullscreen)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, mod=0))
        app._events()
        record("f11_returns_windowed", app.fullscreen is start_fullscreen and pygame.display.get_surface() is not None, app.fullscreen)

        focus_lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        focus_gained = getattr(pygame, "WINDOWFOCUSGAINED", None)
        if focus_lost is not None and focus_gained is not None:
            pygame.event.post(pygame.event.Event(focus_lost))
            pygame.event.post(pygame.event.Event(focus_gained))
            app._events()
        record("focus_cycle_survives", app.running and app.state is GameState.CITY_MAP)
    finally:
        app._save_profile()
        app.audio.shutdown()
        pygame.quit()

    passed = all(check["passed"] for check in checks)
    report = {
        "project": PROJECT_NAME,
        "version": VERSION,
        "build": BUILD_LABEL,
        "checks": checks,
        "summary": {
            "passed": sum(bool(check["passed"]) for check in checks),
            "failed": sum(not bool(check["passed"]) for check in checks),
            "final_result": "PASS" if passed else "FAIL",
        },
    }
    output = result_dir() / "release_input_test.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))
    return 0 if passed else 1
