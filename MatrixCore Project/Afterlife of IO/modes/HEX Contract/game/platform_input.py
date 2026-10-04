from __future__ import annotations

from dataclasses import dataclass

INPUT_KEYBOARD = "keyboard"
INPUT_XBOX = "xbox"

# Logical actions keep the runtime independent from any one platform API.
# Pygame/SDL maps to these today; a future GDK/GameInput bridge can emit the
# same actions without changing menu/game-state logic.
A_CONFIRM = "confirm"
A_BACK = "back"
A_ALT = "alt"
A_INFO = "info"
A_MENU = "menu"
A_VIEW = "view"
A_UP = "up"
A_DOWN = "down"
A_LEFT = "left"
A_RIGHT = "right"
A_LB = "lb"
A_RB = "rb"

MENU_STATES = {
    "TITLE", "SETTINGS", "CONTRACT_BOARD", "HERO_SELECT", "RESTORE_SELECT",
    "LAST_LIGHT", "BOND_EVENT", "LOADOUT_PREP",
}

@dataclass(frozen=True)
class PlatformPrompt:
    primary: str
    secondary: str = ""


def wrap_index(index: int, delta: int, count: int) -> int:
    if count <= 0:
        return 0
    return (int(index) + int(delta)) % int(count)


def prompt_for(state: str, *, mission_active: bool = False, mission_finished: bool = False, paused: bool = False) -> PlatformPrompt:
    if state == "TITLE":
        return PlatformPrompt("[A] SELECT   D-PAD / LEFT STICK NAVIGATE", "[Y] NEW GUILD   [MENU] FIELD GUIDE")
    if state == "SETTINGS":
        return PlatformPrompt("[A] / LEFT-RIGHT CHANGE   D-PAD NAVIGATE", "[B] BACK")
    if state == "CONTRACT_BOARD":
        return PlatformPrompt("[A] SELECT CONTRACT   LEFT-RIGHT CHANGE", "[Y] SETTINGS   [B] BACK")
    if state == "HERO_SELECT":
        return PlatformPrompt("[A] PREPARE   LEFT-RIGHT HERO   [LB]/[RB] ORDER", "[X] RECOVER   [B] BACK")
    if state == "LOADOUT_PREP":
        return PlatformPrompt("[A] DEPLOY   LEFT-RIGHT EQUIPMENT", "[LB]/[RB] SIDEKICKS   [B] BACK")
    if state == "RESTORE_SELECT":
        return PlatformPrompt("[A] RESTORE HERO   LEFT-RIGHT SELECT", "VICTORY RESTORATION IS REQUIRED BEFORE NEXT CONTRACT")
    if state == "LAST_LIGHT":
        return PlatformPrompt("[A] BEGIN NEW GUILD CYCLE", "LAST LIGHT PRESERVES HISTORICAL RECORDS")
    if state == "BOND_EVENT":
        return PlatformPrompt("[A] CONFIRM   LEFT-RIGHT CHOOSE", "RESOLVE THE BOND EVENT TO CONTINUE")
    if state == "MISSION":
        if mission_finished:
            return PlatformPrompt("[A] CONTINUE", "[X] ANALYSIS   [Y] DOSSIER")
        if paused:
            return PlatformPrompt("D-PAD SELECT   [A] CONFIRM", "[B] / [MENU] RESUME")
        if mission_active:
            return PlatformPrompt("[MENU] PAUSE", "[X] ANALYSIS   [Y] DOSSIER")
    return PlatformPrompt("[A] SELECT", "[B] BACK")


def xbox_button_label(action: str) -> str:
    return {
        A_CONFIRM: "A", A_BACK: "B", A_ALT: "X", A_INFO: "Y",
        A_MENU: "MENU", A_VIEW: "VIEW", A_LB: "LB", A_RB: "RB",
        A_UP: "UP", A_DOWN: "DOWN", A_LEFT: "LEFT", A_RIGHT: "RIGHT",
    }.get(action, action.upper())
