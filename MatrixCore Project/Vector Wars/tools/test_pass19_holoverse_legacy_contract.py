#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
SOURCE = MAIN.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
CONTRACT = json.loads((ROOT / "holoverse_legacy_contract.json").read_text(encoding="utf-8"))


def function(name: str) -> ast.FunctionDef:
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def default_for(fn: ast.FunctionDef, arg_name: str):
    names = [arg.arg for arg in fn.args.args]
    idx = names.index(arg_name)
    first_default = len(names) - len(fn.args.defaults)
    if idx < first_default:
        raise AssertionError(f"{arg_name} has no default")
    return ast.literal_eval(fn.args.defaults[idx - first_default])


def require(label: str, cond: bool) -> None:
    if not cond:
        raise AssertionError(label)
    print(f"PASS {label}")


panda = function("get_panda3d_launch_command")
holo = function("get_holoverse_launch_command")
launch = function("launch_from_panda3d")

require("generic Panda launch has no forced QA front", default_for(panda, "auto_mode") is None)
require("Panda helper wrapper has no forced QA front", default_for(launch, "auto_mode") is None)
require("normal auto mode defaults empty", '_get_cli_arg("--auto-mode", "")' in SOURCE)
require("normal launch restores campaign phase", '_apply_combat_mode(phase_progression.active_mode)' in SOURCE)
require("explicit air QA override retained", 'elif auto_mode == "air":' in SOURCE)
require("explicit ground QA override retained", 'auto_mode in {"foot", "ground"}' in SOURCE)
require("explicit ocean QA override retained", 'elif auto_mode == "ocean":' in SOURCE)
require("HoloVerse launch marker supported", '"--holoverse-launch"' in SOURCE and 'HOLOVERSE_EXTERNAL' in SOURCE)
require("HoloVerse return wording enabled for external child", 'if HOLOVERSE_EMBEDDED or HOLOVERSE_EXTERNAL:' in SOURCE)
require("external launch-safe lifecycle separated from in-process embedding", 'in_process_embedded = bool(embedded)' in SOURCE and 'launch_safe = bool(in_process_embedded or PANDA3D_LAUNCH_SAFE)' in SOURCE)
require("external child performs pygame shutdown", 'if not in_process_embedded:\n        pygame.quit()' in SOURCE)
require("host music ownership preserved", 'def holoverse_root_owns_music()' in SOURCE and 'HOLOVERSE_ROOT_OWNS_MUSIC' in SOURCE)
require("shared SFX hook preserved", 'HOLOVERSE_SHARED_SFX_DIR' in SOURCE)
require("user-data override preserved", 'VECTOR_WARS_USER_DATA' in SOURCE)
require("legacy contract identity", CONTRACT.get("compatibility") == "LEGACY" and CONTRACT.get("launch_model") == "external_child_process")
require("legacy contract does not claim native same-window", CONTRACT.get("native_same_window") is False and CONTRACT.get("host_acceptance_required") is True)

# The dedicated HoloVerse helper must call the generic launcher without an auto mode.
holo_text = ast.get_source_segment(SOURCE, holo) or ""
require("HoloVerse helper explicitly avoids QA auto-mode", 'auto_mode=None' in holo_text)
require("HoloVerse helper adds return marker", 'command.insert(2, "--holoverse-launch")' in holo_text)

print("pass19_holoverse_legacy_contract: PASS")
