#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "main.py").read_text(encoding="utf-8")
profile = json.loads((ROOT / "audio_profile.json").read_text(encoding="utf-8"))
manifest = json.loads((ROOT / "assets" / "music" / "music_manifest.json").read_text(encoding="utf-8"))

checks = {
    "music library imported": "from music_library import MUSIC_PHASES, resolve_phase_paths, manifest_track_count" in source,
    "phase pools stored": "self.phase_music_paths" in source,
    "phase switch authority": "def set_music_phase" in source,
    "combat front drives soundtrack": 'AUDIO.set_music_phase({1: "GROUND", 0: "AIR", 2: "OCEAN"}' in source,
    "separate sfx down": "pygame.K_COMMA" in source and "adjust_sfx_volume(-0.05)" in source,
    "separate sfx up": "pygame.K_PERIOD" in source and "adjust_sfx_volume(0.05)" in source,
    "separate music down": "pygame.K_LEFTBRACKET" in source and "adjust_music_volume(-0.05)" in source,
    "separate music up": "pygame.K_RIGHTBRACKET" in source and "adjust_music_volume(0.05)" in source,
    "host music ownership preserved": "holoverse_root_owns_music()" in source,
    "user ground folder": 'USER_MUSIC_DIR / "ground"' in source,
    "user air folder": 'USER_MUSIC_DIR / "air"' in source,
    "user ocean folder": 'USER_MUSIC_DIR / "ocean"' in source,
    "profile manifest declared": profile.get("music_manifest") == "assets/music/music_manifest.json",
    "nine profile tracks": sum(len(v) for v in profile.get("phase_music", {}).values()) == 9,
    "manifest ground three": len(manifest["phases"]["GROUND"]) == 3,
    "manifest air three": len(manifest["phases"]["AIR"]) == 3,
    "manifest ocean three": len(manifest["phases"]["OCEAN"]) == 3,
}

music_fn = source[source.index("    def _start_music"):source.index("\n\nAUDIO = None")]
checks["volume applied after load"] = music_fn.index("pygame.mixer.music.load(chosen)") < music_fn.index("pygame.mixer.music.set_volume(self.effective_music_gain())")

checks["rotation uses monotonic clock"] = "time.monotonic() >= float(getattr(self, \"next_music_rotate_t\"" in source and "self.next_music_rotate_t = time.monotonic() +" in source
checks["runtime self test requires three per phase"] = "all(phase_counts.get(phase, 0) >= 3 for phase in MUSIC_PHASES)" in source

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
if failed:
    raise SystemExit("pass15 failures: " + ", ".join(failed))
print("pass15_phase_music: PASS")
