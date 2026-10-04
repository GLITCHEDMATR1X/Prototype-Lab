"""State-aware score routing and deterministic score assets for Entropy Pass 28.

This module deliberately has no pygame dependency.  Campaign/collapse state chooses
one musical state; the pygame streaming layer in ``space_core.py`` owns playback.
The existing user-supplied MCF24 track remains untouched and is the expedition theme.
"""
from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from typing import Iterable, Sequence

SCORE_GENERATOR_VERSION = "entropy-score-v1"
SAMPLE_RATE = 48_000
LOOP_SECONDS = 20.0

STATE_HOME = "home"
STATE_SHIP_RECOVERY = "ship_recovery"
STATE_EXPEDITION = "expedition"
STATE_COLLAPSE = "collapse"
STATE_GLEEBS = "gleebs"
STATE_SILENCE = "silence"

STATE_TRACKS = {
    STATE_HOME: "score_home_signal.wav",
    STATE_SHIP_RECOVERY: "score_ship_recovery.wav",
    STATE_EXPEDITION: "MCF24.mp3",
    STATE_COLLAPSE: "score_collapse_pressure.wav",
    STATE_GLEEBS: "score_gleebs_link.wav",
}

# Per-state trim is intentionally below the ship/effects category.  User Music and
# Master settings remain independent and are multiplied at runtime.
STATE_BASE_VOLUME = {
    STATE_HOME: 0.54,
    STATE_SHIP_RECOVERY: 0.50,
    STATE_EXPEDITION: 0.58,
    STATE_COLLAPSE: 0.62,
    STATE_GLEEBS: 0.56,
    STATE_SILENCE: 0.0,
}

# MIDI chord sets.  The generator crossfades these cyclically and snaps each
# oscillator to an integer number of cycles over the file, giving clean loop joins.
SCORE_CONFIG = {
    STATE_HOME: {
        "chords": ((50, 57, 64), (46, 53, 62), (48, 55, 62), (45, 52, 60)),
        "pad": 0.34, "pulse": 0.055, "shimmer": 0.045, "beat_count": 10,
        "stereo_phase": 0.31,
    },
    STATE_SHIP_RECOVERY: {
        "chords": ((40, 47, 52), (41, 48, 53), (43, 50, 55), (38, 45, 50)),
        "pad": 0.28, "pulse": 0.10, "shimmer": 0.025, "beat_count": 16,
        "stereo_phase": 0.53,
    },
    STATE_COLLAPSE: {
        "chords": ((38, 45, 50), (37, 44, 49), (36, 43, 48), (34, 41, 46)),
        "pad": 0.25, "pulse": 0.20, "shimmer": 0.035, "beat_count": 32,
        "stereo_phase": 0.79,
    },
    STATE_GLEEBS: {
        "chords": ((48, 55, 62), (50, 57, 64), (52, 59, 66), (55, 62, 69)),
        "pad": 0.33, "pulse": 0.045, "shimmer": 0.09, "beat_count": 8,
        "stereo_phase": 1.07,
    },
}


def midi_hz(note: int) -> float:
    return 440.0 * (2.0 ** ((int(note) - 69) / 12.0))


def _snap_frequency(freq: float, duration: float = LOOP_SECONDS) -> float:
    """Snap to a whole number of cycles over the loop duration."""
    return max(1.0 / duration, round(float(freq) * duration) / duration)


def _circular_distance(a: float, b: float, period: float) -> float:
    d = abs(a - b) % period
    return min(d, period - d)


def _chord_weight(progress: float, chord_index: int, chord_count: int) -> float:
    """Raised-cosine crossfade with cyclic wraparound."""
    center = float(chord_index)
    dist = _circular_distance(progress, center, float(chord_count))
    if dist >= 1.0:
        return 0.0
    return 0.5 + 0.5 * math.cos(math.pi * dist)


def _render_score(state: str, out_path: Path) -> dict:
    cfg = SCORE_CONFIG[state]
    chords: Sequence[Sequence[int]] = cfg["chords"]
    chord_count = len(chords)
    n = int(SAMPLE_RATE * LOOP_SECONDS)
    duration = LOOP_SECONDS
    beat_count = int(cfg["beat_count"])
    stereo_phase = float(cfg["stereo_phase"])

    # Precompute oscillators.  Snapped frequencies make the first and last sample
    # meet cleanly even after many layers are summed.
    osc = []
    for ci, chord in enumerate(chords):
        voices = []
        for vi, note in enumerate(chord):
            freq = _snap_frequency(midi_hz(note))
            phase_l = 0.21 * ci + 0.37 * vi
            phase_r = phase_l + stereo_phase * (0.22 + 0.08 * vi)
            voices.append((freq, phase_l, phase_r))
        osc.append(voices)

    frames = bytearray()
    peak = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        loop_phase = t / duration
        progress = loop_phase * chord_count
        beat_phase = (loop_phase * beat_count) % 1.0
        # Fast attack / exponential-ish decay, periodic at the loop boundary.
        pulse_env = (1.0 - beat_phase) ** 4
        slow = 0.72 + 0.28 * math.sin(math.tau * loop_phase - 0.7)

        left = 0.0
        right = 0.0
        root_left = 0.0
        root_right = 0.0
        shimmer_l = 0.0
        shimmer_r = 0.0

        for ci, voices in enumerate(osc):
            weight = _chord_weight(progress, ci, chord_count)
            if weight <= 0.0:
                continue
            for vi, (freq, phase_l, phase_r) in enumerate(voices):
                voice_scale = (1.0, 0.72, 0.52)[min(vi, 2)]
                l = math.sin(math.tau * freq * t + phase_l)
                r = math.sin(math.tau * freq * t + phase_r)
                left += l * weight * voice_scale
                right += r * weight * voice_scale
                if vi == 0:
                    root_left += l * weight
                    root_right += r * weight
                if vi == 2:
                    shimmer_freq = _snap_frequency(freq * 4.0)
                    shimmer_l += math.sin(math.tau * shimmer_freq * t + phase_l * 1.7) * weight
                    shimmer_r += math.sin(math.tau * shimmer_freq * t + phase_r * 1.7) * weight

        left = left * float(cfg["pad"]) * 0.36 * slow
        right = right * float(cfg["pad"]) * 0.36 * slow
        left += root_left * float(cfg["pulse"]) * pulse_env
        right += root_right * float(cfg["pulse"]) * pulse_env
        shimmer_env = (0.5 + 0.5 * math.sin(math.tau * loop_phase * 2.0 + 0.4)) ** 4
        left += shimmer_l * float(cfg["shimmer"]) * shimmer_env * 0.30
        right += shimmer_r * float(cfg["shimmer"]) * shimmer_env * 0.30

        # A very low sub tone gives the score body without competing with SFX.
        sub_freq = _snap_frequency(midi_hz(chords[0][0] - 12))
        sub = math.sin(math.tau * sub_freq * t + 0.15) * 0.055
        left += sub
        right += sub * 0.96

        left = max(-0.92, min(0.92, left))
        right = max(-0.92, min(0.92, right))
        peak = max(peak, abs(left), abs(right))
        frames.extend(struct.pack("<hh", int(left * 32767), int(right * 32767)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames)

    return {
        "state": state,
        "file": out_path.name,
        "sample_rate": SAMPLE_RATE,
        "channels": 2,
        "duration": LOOP_SECONDS,
        "peak": round(peak, 6),
    }


def ensure_score_assets(music_root: Path | str, force: bool = False) -> dict:
    root = Path(music_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "score_manifest.json"
    expected = {STATE_TRACKS[state] for state in SCORE_CONFIG}
    regenerate = bool(force)
    if not regenerate:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            regenerate = manifest.get("generator_version") != SCORE_GENERATOR_VERSION
        except Exception:
            regenerate = True
    if not regenerate:
        regenerate = any(not (root / name).is_file() for name in expected)

    rendered = []
    if regenerate:
        for state in (STATE_HOME, STATE_SHIP_RECOVERY, STATE_COLLAPSE, STATE_GLEEBS):
            rendered.append(_render_score(state, root / STATE_TRACKS[state]))
        manifest = {
            "generator_version": SCORE_GENERATOR_VERSION,
            "sample_rate": SAMPLE_RATE,
            "loop_seconds": LOOP_SECONDS,
            "expedition_source": STATE_TRACKS[STATE_EXPEDITION],
            "generated": rendered,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    return manifest


def score_state_for(mission, *, failure_active: bool = False, campaign_complete_active: bool = False) -> str:
    """Resolve the one authoritative music state for the current run."""
    if failure_active:
        return STATE_SILENCE
    if campaign_complete_active or bool(getattr(mission, "campaign_complete", False)):
        return STATE_GLEEBS

    phase = str(getattr(mission, "campaign_phase", "expedition"))
    if phase == "ship_recovery":
        return STATE_SHIP_RECOVERY
    if phase in ("delivery", "complete"):
        return STATE_GLEEBS

    collapse = str(getattr(mission, "collapse_state", "STABLE")).upper()
    if collapse in ("CRITICAL", "SUPERNOVA", "BLACK HOLE"):
        return STATE_COLLAPSE
    if phase == "home":
        return STATE_HOME
    return STATE_EXPEDITION
