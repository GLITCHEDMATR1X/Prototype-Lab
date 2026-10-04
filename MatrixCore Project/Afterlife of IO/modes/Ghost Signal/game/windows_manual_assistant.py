from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pygame

from audio.audio_manager import AudioManager
from game.results import result_dir
from game.version import BUILD_LABEL, PROJECT_NAME, VERSION


@dataclass(frozen=True)
class AcceptanceStep:
    key: str
    title: str
    instruction: str
    requirement: str = ""


STEPS = (
    AcceptanceStep(
        "windowed_launch",
        "WINDOWED LAUNCH",
        "Confirm the bordered game window is visible, responsive, and correctly scaled.",
    ),
    AcceptanceStep(
        "fullscreen_round_trip",
        "FULLSCREEN ROUND-TRIP",
        "Press F11 to enter fullscreen, then F11 again to return. Confirm neither transition black-screens or loses input.",
        "fullscreen_round_trip",
    ),
    AcceptanceStep(
        "alt_tab_recovery",
        "ALT+TAB RECOVERY",
        "Alt+Tab away from this window and return. Confirm rendering, mouse, keyboard, and audio recover.",
        "focus_cycle",
    ),
    AcceptanceStep(
        "audible_output",
        "AUDIBLE OUTPUT",
        "Press P to replay the cue sequence. Confirm ambience, interface, hack, Gleebs, memory, and capture cues are audible and undistorted.",
        "audio_available",
    ),
    AcceptanceStep(
        "settings_persistence",
        "SETTINGS AND SAVE RELAUNCH",
        "Confirm mute/volume/fullscreen settings and a mid-campaign save survived a complete executable relaunch.",
    ),
    AcceptanceStep(
        "blank_human_playthrough",
        "BLANK-SAVE HUMAN ROUTE",
        "Confirm a human completed all 11 buildings, one Gleebs lockout, all 11 memories, and the Chapter One finale from a blank save.",
    ),
    AcceptanceStep(
        "migrated_human_playthrough",
        "MIGRATED-SAVE HUMAN ROUTE",
        "Confirm a historic profile migrated, resumed, completed the Industrial Grid, and reached the Chapter One Complete title.",
    ),
    AcceptanceStep(
        "clean_exit_no_crash",
        "CLEAN EXIT",
        "Confirm the tested build exits normally and produced no crash.log.",
    ),
)


class ManualAcceptanceAssistant:
    def __init__(self, report_path: Path, auto_test: bool = False, screenshot_path: Path | None = None) -> None:
        self.report_path = report_path
        self.auto_test = bool(auto_test)
        self.screenshot_path = screenshot_path
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(f"{PROJECT_NAME} — WINDOWS V1 ACCEPTANCE")
        self.windowed_size = (1280, 720)
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE | pygame.DOUBLEBUF)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 30)
        self.small = pygame.font.Font(None, 23)
        self.title_font = pygame.font.Font(None, 52)
        self.audio = AudioManager(disabled=False)
        self.results: dict[str, bool] = {}
        self.notes: dict[str, str] = {}
        self.index = 0
        self.running = True
        self.fullscreen_toggles = 0
        self.focus_lost = False
        self.focus_gained_after_loss = False
        self.sequence_started = False
        self.started_at = time.time()

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE | pygame.DOUBLEBUF)
        self.fullscreen_toggles += 1

    def _play_audio_sequence(self) -> None:
        self.sequence_started = True
        self.audio.set_scene("city")
        for cue in (
            "ui_confirm",
            "hack_clean",
            "hack_noisy",
            "gleebs_alarm",
            "memory_restore",
            "building_capture",
        ):
            self.audio.play(cue)

    def _requirement_met(self, requirement: str) -> bool:
        if requirement == "fullscreen_round_trip":
            return self.fullscreen_toggles >= 2 and not self.fullscreen
        if requirement == "focus_cycle":
            return self.focus_lost and self.focus_gained_after_loss
        if requirement == "audio_available":
            return self.audio.available and self.sequence_started
        return True

    def _record(self, passed: bool) -> None:
        step = STEPS[self.index]
        requirement_met = self._requirement_met(step.requirement)
        accepted = bool(passed and requirement_met)
        self.results[step.key] = accepted
        if passed and not requirement_met:
            self.notes[step.key] = f"Required evidence not observed: {step.requirement}"
        self.index += 1
        if self.index >= len(STEPS):
            self.running = False

    @staticmethod
    def _wrap(text: str, width: int = 84) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        count = 0
        for word in words:
            projected = count + len(word) + (1 if current else 0)
            if current and projected > width:
                lines.append(" ".join(current))
                current = [word]
                count = len(word)
            else:
                current.append(word)
                count = projected
        if current:
            lines.append(" ".join(current))
        return lines

    def _render(self) -> None:
        self.screen.fill((3, 7, 11))
        width, height = self.screen.get_size()
        pygame.draw.rect(self.screen, (18, 32, 38), (46, 42, width - 92, height - 84), border_radius=12)
        pygame.draw.rect(self.screen, (72, 230, 245), (46, 42, width - 92, height - 84), 2, border_radius=12)
        heading = self.title_font.render("GHOST SIGNAL: UTOPIA — WINDOWS ACCEPTANCE", True, (218, 250, 255))
        self.screen.blit(heading, (78, 74))
        progress = self.small.render(f"RC3 OPERATOR GATE • STEP {min(self.index + 1, len(STEPS))}/{len(STEPS)}", True, (124, 176, 188))
        self.screen.blit(progress, (82, 132))
        if self.index < len(STEPS):
            step = STEPS[self.index]
            title = self.font.render(step.title, True, (168, 255, 228))
            self.screen.blit(title, (82, 190))
            y = 246
            for line in self._wrap(step.instruction):
                rendered = self.font.render(line, True, (216, 226, 230))
                self.screen.blit(rendered, (82, y))
                y += 36
            if step.requirement:
                status = self._requirement_met(step.requirement)
                evidence = self.small.render(
                    f"REQUIRED EVIDENCE: {step.requirement.replace('_', ' ').upper()} — {'OBSERVED' if status else 'PENDING'}",
                    True,
                    (110, 240, 160) if status else (255, 185, 90),
                )
                self.screen.blit(evidence, (82, y + 22))
            if step.key == "audible_output":
                replay = self.small.render("P — PLAY/REPLAY AUDIO SEQUENCE", True, (172, 206, 255))
                self.screen.blit(replay, (82, y + 62))
            controls = self.font.render("Y — PASS     N — FAIL     ESC — CANCEL", True, (245, 225, 140))
            self.screen.blit(controls, (82, height - 126))
        pygame.display.flip()

    def _write_report(self, contract_only: bool = False) -> int:
        checks = [{"name": step.key, "passed": bool(self.results.get(step.key, False)), "note": self.notes.get(step.key, "")} for step in STEPS]
        all_passed = all(item["passed"] for item in checks)
        native_windows = sys.platform == "win32"
        operator_confirmed = all_passed and not contract_only and native_windows
        final_result = "PASS" if operator_confirmed else ("CONTRACT_PASS" if contract_only and all_passed else "FAIL")
        report = {
            "project": PROJECT_NAME,
            "version": VERSION,
            "build": BUILD_LABEL,
            "report_type": "native_windows_manual_acceptance" if not contract_only else "manual_acceptance_contract_test",
            "platform": platform.platform(),
            "sys_platform": sys.platform,
            "python": platform.python_version(),
            "pygame": pygame.version.ver,
            "sdl": ".".join(str(v) for v in pygame.get_sdl_version()),
            "display_driver": pygame.display.get_driver(),
            "audio": self.audio.snapshot(),
            "operator_confirmed": operator_confirmed,
            "checks": checks,
            "summary": {
                "passed": sum(bool(item["passed"]) for item in checks),
                "failed": sum(not bool(item["passed"]) for item in checks),
                "final_result": final_result,
            },
            "started_at": self.started_at,
            "completed_at": time.time(),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["summary"]))
        return 0 if final_result in ("PASS", "CONTRACT_PASS") else 1

    def run(self) -> int:
        if self.auto_test:
            self.fullscreen_toggles = 2
            self.focus_lost = True
            self.focus_gained_after_loss = True
            self.sequence_started = True
            # Dummy audio may be available and is enough for the harness contract.
            for step in STEPS:
                self.results[step.key] = True
            self.index = 3
            self._render()
            if self.screenshot_path is not None:
                self.screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.screen, self.screenshot_path)
            result = self._write_report(contract_only=True)
            self.audio.shutdown()
            pygame.quit()
            return result

        if sys.platform != "win32":
            self.notes["platform"] = "Native Windows is required for operator acceptance."
            result = self._write_report(contract_only=False)
            self.audio.shutdown()
            pygame.quit()
            return result

        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.windowed_size = (max(960, event.w), max(540, event.h))
                    self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE | pygame.DOUBLEBUF)
                elif event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                    self.focus_lost = True
                elif event.type == getattr(pygame, "WINDOWFOCUSGAINED", -1):
                    if self.focus_lost:
                        self.focus_gained_after_loss = True
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_F11:
                        self._toggle_fullscreen()
                    elif event.key == pygame.K_p and self.index < len(STEPS) and STEPS[self.index].key == "audible_output":
                        self._play_audio_sequence()
                    elif event.key == pygame.K_y:
                        self._record(True)
                    elif event.key == pygame.K_n:
                        self._record(False)
            self._render()
        result = self._write_report(contract_only=False)
        self.audio.shutdown()
        pygame.quit()
        return result


def run_windows_manual_assistant(report_path: Path | None = None, auto_test: bool = False, screenshot_path: Path | None = None) -> int:
    destination = report_path or (result_dir() / "windows_manual_acceptance.json")
    return ManualAcceptanceAssistant(destination, auto_test=auto_test, screenshot_path=screenshot_path).run()
