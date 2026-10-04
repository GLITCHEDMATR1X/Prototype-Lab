from __future__ import annotations

import json
from pathlib import Path

MUSIC_PHASES = ("GROUND", "AIR", "OCEAN")
MUSIC_EXTENSIONS = (".wav", ".ogg", ".mp3")
MANIFEST_RELATIVE_PATH = Path("assets") / "music" / "music_manifest.json"


def _normalize_phase(phase: str) -> str:
    value = str(phase or "GROUND").strip().upper()
    return value if value in MUSIC_PHASES else "GROUND"


def load_music_manifest(project_root: Path) -> dict:
    path = Path(project_root) / MANIFEST_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "", "phases": {phase: [] for phase in MUSIC_PHASES}}
    phases = raw.get("phases") if isinstance(raw, dict) else None
    if not isinstance(phases, dict):
        phases = {}
    clean = {}
    for phase in MUSIC_PHASES:
        entries = phases.get(phase, [])
        if not isinstance(entries, list):
            entries = []
        valid = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rel = str(entry.get("file", "")).strip().replace("\\", "/")
            if not rel:
                continue
            valid.append({
                "id": str(entry.get("id", "")).strip() or Path(rel).stem,
                "title": str(entry.get("title", "")).strip() or Path(rel).stem,
                "file": rel,
            })
        clean[phase] = valid
    return {"schema": str(raw.get("schema", "")), "phases": clean}


def manifest_phase_paths(project_root: Path, phase: str) -> list[str]:
    root = Path(project_root)
    manifest = load_music_manifest(root)
    normalized = _normalize_phase(phase)
    paths = []
    for entry in manifest["phases"].get(normalized, []):
        candidate = root / entry["file"]
        if candidate.is_file() and candidate.suffix.lower() in MUSIC_EXTENSIONS:
            paths.append(str(candidate))
    return paths


def user_phase_paths(user_music_root: Path, phase: str) -> list[str]:
    directory = Path(user_music_root) / _normalize_phase(phase).lower()
    if not directory.is_dir():
        return []
    return [str(p) for p in sorted(directory.iterdir()) if p.is_file() and p.suffix.lower() in MUSIC_EXTENSIONS]


def resolve_phase_paths(project_root: Path, user_music_root: Path, phase: str) -> list[str]:
    """Player phase overrides win as a pool; otherwise use the shipped manifest."""
    user = user_phase_paths(user_music_root, phase)
    return user if user else manifest_phase_paths(project_root, phase)


def manifest_track_count(project_root: Path) -> dict[str, int]:
    manifest = load_music_manifest(Path(project_root))
    return {phase: len(manifest["phases"].get(phase, [])) for phase in MUSIC_PHASES}
