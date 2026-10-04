"""Pure helpers for Gleebs' in-world terminal presence.

Kept Panda3D-free so approach/fade behavior can be regression-tested without a
rendering runtime.  Runtime code owns NodePaths; this module only owns the
proximity curve and temporal smoothing contract.
"""
from __future__ import annotations

import math


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def smoothstep01(value: float) -> float:
    t = clamp01(value)
    return t * t * (3.0 - 2.0 * t)


def terminal_proximity_alpha(distance: float, *, full_distance: float = 6.5, hidden_distance: float = 14.5) -> float:
    """Return 0..1 visibility from horizontal distance to Gleebs' terminal.

    ``full_distance`` is where the hologram has reached full visibility.
    ``hidden_distance`` is where it is fully absent.  The curve is continuous,
    so crossing either gameplay range cannot create a one-frame pop.
    """
    near = max(0.0, float(full_distance))
    far = max(near + 0.001, float(hidden_distance))
    d = max(0.0, float(distance))
    return smoothstep01((far - d) / (far - near))


def approach_fade(current: float, target: float, dt: float, *, response: float = 6.5) -> float:
    """Frame-rate-independent exponential approach for a hologram fade."""
    c = clamp01(current)
    t = clamp01(target)
    step = max(0.0, float(dt))
    if step <= 0.0:
        return c
    blend = 1.0 - math.exp(-max(0.01, float(response)) * step)
    return clamp01(c + (t - c) * blend)
