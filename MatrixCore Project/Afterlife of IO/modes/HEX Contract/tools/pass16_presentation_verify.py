from __future__ import annotations

import ast
import hashlib
import json
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SIM_GAMEPLAY_AST = "29f5c79b57a341c8509bf2185628a85faf55f25837853407201e8dd93fb113ae"
BASELINE_WORLD_GEOMETRY_DIGEST = "86a734ac04d5dd5340cae1e040321d5e32ee08fc50baa236e94e544db50dad58"
BASELINE_HASHES = {
    "game/data.py": "eb2262c00d24519e075e91e4a55bf2f4aa44e02b0e09475658f10c5b5db2b159",
    "game/world.py": "3a3d1a345e5a1f2b98e57f425324bcbe3e88bc33c35e27f92146f7fa993f56b4",
    "game/world_data.py": "fd93b9ffa7e36bb4a406e78fc57e23ec814cdbc0d10be8e2e09532c84364a49b",
    "game/actors.py": "8be771ef389f8e0f739eebc5de59148c4671ca551f39d36ea44fe5fec7172a8e",
    "game/actor_visuals.py": "bffe05ba33677bfc59b322495ef233f739c5707d5bde1c46c5e6473de8a3a881",
}
EXPECTED_CUES = {
    "hero_melee", "hero_ranged", "hero_ability", "enemy_melee", "enemy_ranged",
    "impact_enemy", "impact_hero", "enemy_down", "cover_hit", "cover_break",
    "objective", "civilian_link", "boss_intro", "boss_phase", "boss_special", "boss_down",
}
EXPECTED_AMBIENCE = {"ambience_guild", "ambience_purge", "ambience_recovery", "ambience_rescue"}


class StripPresentation(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        if node.name in {"emit_presentation", "consume_presentation_events"}:
            return None
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        t = node.target
        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self" and t.attr == "presentation_events":
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        for t in node.targets:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self" and t.attr == "presentation_events":
                return None
        return self.generic_visit(node)

    def visit_Expr(self, node):
        c = node.value
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id == "self" and c.func.attr == "emit_presentation":
            return None
        return self.generic_visit(node)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gameplay_digest(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree = StripPresentation().visit(tree)
    ast.fix_missing_locations(tree)
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode("utf-8")).hexdigest()


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
    audio_source = (ROOT / "game/audio.py").read_text(encoding="utf-8")
    app_source = (ROOT / "game/app.py").read_text(encoding="utf-8")
    render_source = (ROOT / "game/render.py").read_text(encoding="utf-8")
    sim_source = (ROOT / "game/sim.py").read_text(encoding="utf-8")

    gameplay = {rel: sha(ROOT / rel) == digest for rel, digest in BASELINE_HASHES.items() if rel != "game/world_data.py"}
    gameplay["game/world_data.py geometry"] = world_geometry_digest(ROOT / "game" / "world_data.py") == BASELINE_WORLD_GEOMETRY_DIGEST
    gameplay["game/sim.py gameplay AST"] = gameplay_digest(ROOT / "game/sim.py") == BASELINE_SIM_GAMEPLAY_AST
    assert all(gameplay.values()), gameplay

    source_checks = {
        "optional_streamed_music": "pygame.mixer.music.load" in audio_source,
        "music_folder_scan": "assets\" / \"music" in audio_source,
        "mission_context_audio": "def set_context" in audio_source and "ambience_{quest_key}" in audio_source,
        "audio_device_failure_safe": "if not self.enabled" in audio_source,
        "music_setting": '"music_volume"' in app_source and '("MUSIC VOLUME", "music_volume"' in render_source,
        "presentation_queue": "consume_presentation_events" in app_source and "emit_presentation" in sim_source,
        "contract_atmosphere": "def _draw_contract_atmosphere" in render_source,
        "projectile_trails": "tail = p.pos - direction * 26" in render_source,
        "hit_feedback": "hit_flash" in render_source and "pygame.draw.circle" in render_source,
        "pass16_runtime_test": "def pass16_test" in app_source and "--pass16-test" in app_source,
    }
    assert all(source_checks.values()), source_checks

    missing_cues = [cue for cue in sorted(EXPECTED_CUES) if f'"{cue}"' not in audio_source or f'emit_presentation("{cue}")' not in sim_source]
    assert not missing_cues, missing_cues
    missing_ambience = [cue for cue in sorted(EXPECTED_AMBIENCE) if f'"{cue}"' not in audio_source]
    assert not missing_ambience, missing_ambience

    audio_dir = ROOT / "assets/generated/sfx"
    wav_checks = {}
    for key in sorted(EXPECTED_CUES | EXPECTED_AMBIENCE):
        path = audio_dir / f"{key}.wav"
        ok = path.exists() and path.stat().st_size > 400
        meta = {}
        if ok:
            with wave.open(str(path), "rb") as w:
                meta = {"channels": w.getnchannels(), "rate": w.getframerate(), "frames": w.getnframes()}
                ok = w.getnchannels() == 1 and w.getframerate() == 22050 and w.getnframes() > 1000
        wav_checks[key] = {"pass": ok, **meta}
    assert all(v["pass"] for v in wav_checks.values()), wav_checks

    music_dir = ROOT / "assets/music"
    music_files = sorted(p.name for p in music_dir.iterdir() if p.suffix.lower() in {".wav", ".ogg", ".mp3"}) if music_dir.exists() else []
    report = {
        "pass16_presentation_audio_static": "PASS",
        "gameplay_authority_preserved": gameplay,
        "source_contracts": source_checks,
        "combat_cues": sorted(EXPECTED_CUES),
        "ambience_profiles": sorted(EXPECTED_AMBIENCE),
        "wav_assets": wav_checks,
        "music_library": {"path": "assets/music", "bundled_tracks": music_files, "optional": True, "formats": ["wav", "ogg", "mp3"]},
    }
    out = ROOT / "verification/reports/pass16_presentation_audio_static.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
