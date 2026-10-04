from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BASELINE_HASHES = {
    "game/data.py": "eb2262c00d24519e075e91e4a55bf2f4aa44e02b0e09475658f10c5b5db2b159",
    "game/world.py": "3a3d1a345e5a1f2b98e57f425324bcbe3e88bc33c35e27f92146f7fa993f56b4",
    "game/world_data.py": "fd93b9ffa7e36bb4a406e78fc57e23ec814cdbc0d10be8e2e09532c84364a49b",
}


BASELINE_SIM_GAMEPLAY_AST = "29f5c79b57a341c8509bf2185628a85faf55f25837853407201e8dd93fb113ae"
BASELINE_WORLD_GEOMETRY_DIGEST = "86a734ac04d5dd5340cae1e040321d5e32ee08fc50baa236e94e544db50dad58"


class _StripPresentation(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        if node.name in {"emit_presentation", "consume_presentation_events"}:
            return None
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        target = node.target
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self" and target.attr == "presentation_events":
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self" and target.attr == "presentation_events":
                return None
        return self.generic_visit(node)

    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "self" and call.func.attr == "emit_presentation":
            return None
        return self.generic_visit(node)


def gameplay_ast_sha256(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree = _StripPresentation().visit(tree)
    ast.fix_missing_locations(tree)
    payload = ast.dump(tree, include_attributes=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_constants(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    return values


def world_geometry_digest(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    keys = ("WORLD_RECT", "MAX_ACTOR_RADIUS", "MIN_CLEAR_GAP", "PREFERRED_CLEAR_GAP", "SPAWN_CLEARANCE", "EDGE_CLEARANCE", "PREFABS", "LAYOUTS")
    data = {key: values[key] for key in keys}
    for layout in data["LAYOUTS"].values():
        for obj in layout["objects"]:
            obj.pop("texture", None)
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    actors_path = ROOT / "game" / "actors.py"
    visuals_path = ROOT / "game" / "actor_visuals.py"
    source = actors_path.read_text(encoding="utf-8")
    visuals = load_constants(visuals_path)

    unchanged = {rel: sha256(ROOT / rel) == digest for rel, digest in BASELINE_HASHES.items() if rel != "game/world_data.py"}
    unchanged["game/world_data.py geometry"] = world_geometry_digest(ROOT / "game" / "world_data.py") == BASELINE_WORLD_GEOMETRY_DIGEST
    unchanged["game/sim.py gameplay AST"] = gameplay_ast_sha256(ROOT / "game" / "sim.py") == BASELINE_SIM_GAMEPLAY_AST
    assert all(unchanged.values()), unchanged

    required_tokens = {
        "filled_limb_helper": "def _filled_limb",
        "boot_helper": "def _boot",
        "armor_panel_helper": "def _armor_panel",
        "civilian_style_authority": "CIVILIAN_STYLE",
        "archive_pilgrim_costume": "Archive pilgrim",
        "choir_defector_costume": "Choir defector",
        "relic_medic_costume": "Relic medic",
        "ash_saint_body": 'boss_id == "ash_saint"',
        "mirror_abbot_body": 'boss_id == "mirror_abbot"',
        "last_conductor_body": 'boss_id == "last_conductor"',
    }
    token_checks = {name: token in source for name, token in required_tokens.items()}
    assert all(token_checks.values()), token_checks

    filled_limb_calls = source.count("_filled_limb(") - 1
    armor_panel_calls = source.count("_armor_panel(") - 1
    boot_calls = source.count("_boot(") - 1
    assert filled_limb_calls >= 22, filled_limb_calls
    assert boot_calls >= 7, boot_calls
    assert armor_panel_calls >= 3, armor_panel_calls

    hero_r = visuals["HERO_VISUAL_RADIUS"]
    enemy_r = visuals["ENEMY_VISUAL_RADIUS"]
    boss_r = visuals["BOSS_VISUAL_RADIUS"]
    min_gap = visuals["PASS14_MIN_WORLD_GAP"]
    civ_r = visuals["CIVILIAN_VISUAL_RADIUS"]
    max_diameter = max(boss_r.values()) * 2
    margin = min_gap - max_diameter
    assert max_diameter < min_gap
    assert margin >= 20
    assert max(hero_r.values()) * 2 < min_gap
    assert max(enemy_r.values()) * 2 < min_gap
    assert civ_r * 2 < min_gap

    report = {
        "pass15_actor_identity_static": "PASS",
        "baseline_gameplay_authority_preserved": unchanged,
        "source_contracts": token_checks,
        "filled_limb_calls": filled_limb_calls,
        "boot_calls": boot_calls,
        "armor_panel_calls": armor_panel_calls,
        "hero_visual_radius": hero_r,
        "enemy_visual_radius": enemy_r,
        "boss_visual_radius": boss_r,
        "civilian_visual_radius": civ_r,
        "pass14_min_gap": min_gap,
        "max_actor_visual_diameter": max_diameter,
        "clearance_margin": margin,
        "presentation_rules": visuals.get("ACTOR_PRESENTATION_RULES", {}),
    }
    target = ROOT / "verification" / "reports" / "pass15_actor_identity_static.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
