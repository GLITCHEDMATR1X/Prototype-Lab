#!/usr/bin/env python3
from __future__ import annotations
import tempfile
import wave
import sys
from array import array
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from music_library import MUSIC_PHASES, load_music_manifest, manifest_track_count, resolve_phase_paths

manifest = load_music_manifest(ROOT)
counts = manifest_track_count(ROOT)
assert counts == {"GROUND": 3, "AIR": 3, "OCEAN": 3}, counts
seen = set()
for phase in MUSIC_PHASES:
    paths = resolve_phase_paths(ROOT, ROOT / "__no_user_music__", phase)
    assert len(paths) == 3, (phase, paths)
    for raw in paths:
        path = Path(raw)
        assert path.is_file(), path
        assert path not in seen, path
        seen.add(path)
        with wave.open(str(path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 22050
            duration = wf.getnframes() / wf.getframerate()
            assert duration >= 10.0, duration
            frames = wf.readframes(min(wf.getnframes(), 22050))
        samples = array('h'); samples.frombytes(frames)
        assert max(abs(v) for v in samples) > 100, path
assert len(seen) == 9

with tempfile.TemporaryDirectory() as td:
    user = Path(td)
    phase_dir = user / "ground"
    phase_dir.mkdir(parents=True)
    override = phase_dir / "my_ground.ogg"
    override.write_bytes(b"override")
    assert resolve_phase_paths(ROOT, user, "GROUND") == [str(override)]

print("music_library: PASS")
