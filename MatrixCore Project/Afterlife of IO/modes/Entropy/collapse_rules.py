"""Deterministic collapse/failure rules for Entropy Pass 21.

This module deliberately has no pygame dependency so timeline, warning, and
hull-pressure behavior can be regression tested in any build environment.
"""
from __future__ import annotations

COLLAPSE_DURATION = 60.0
SINGULARITY_DELAY = 120.0
SUPERNOVA_SHOCK_DAMAGE = 24
POST_SUPERNOVA_DAMAGE_PER_SECOND = 0.45
BLACK_HOLE_DAMAGE_PER_SECOND = 12.0


def stage_for_remaining(remaining: float, duration: float = COLLAPSE_DURATION) -> str:
    remaining = max(0.0, float(remaining))
    duration = max(0.001, float(duration))
    ratio = remaining / duration
    if remaining <= 0.0:
        return "SUPERNOVA"
    if ratio <= 0.20:
        return "CRITICAL"
    if ratio <= 0.50:
        return "UNSTABLE"
    return "STABLE"


def warning_text(stage: str) -> str:
    stage = str(stage).upper()
    return {
        "UNSTABLE": "STELLAR SHEAR RISING — PRIORITIZE THE PRIMARY SIGNAL",
        "CRITICAL": "COLLAPSE CRITICAL — RETURN TO ORBIT AND PREPARE TO WARP",
        "SUPERNOVA": "SUPERNOVA SHOCK — LANDING LOCKED / SINGULARITY FORMING",
        "BLACK HOLE": "EVENT HORIZON ACTIVE — WARP OR LOSE THE SHIP",
    }.get(stage, "")


def hull_damage_rate(*, triggered: bool, post_supernova: bool, blackhole_active: bool) -> float:
    if blackhole_active:
        return BLACK_HOLE_DAMAGE_PER_SECOND
    if post_supernova:
        return POST_SUPERNOVA_DAMAGE_PER_SECOND
    if triggered:
        return POST_SUPERNOVA_DAMAGE_PER_SECOND * 0.35
    return 0.0


def timer_label(stage: str, singularity_countdown: bool = False) -> str:
    if str(stage).upper() == "BLACK HOLE":
        return "EVENT HORIZON"
    if singularity_countdown:
        return "SINGULARITY"
    return "COLLAPSE"


def format_timer(seconds: float) -> str:
    seconds = max(0, int(float(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
