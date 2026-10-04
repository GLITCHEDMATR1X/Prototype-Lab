"""Pass 52 — feet that match the ground.

Every walk / jog / sprint clip in the animation library is made "in place": the body stays
still and the planted foot sweeps backward under it. The speed of that sweep is the speed
the clip was made for. If a character moves at any other speed while the clip plays at its
normal rate, the planted foot slides:
    - move slower than the sweep  -> running in place (the old human jog: clip 5.9 m/s, moved 2.5)
    - move faster than the sweep  -> ice skating (the old human walk: clip 0.93 m/s, moved 1.35)

So from Pass 52 NO clip is played by time any more. Every character's walk cycle is driven by
the ground it actually covers:

    cycle advance = distance moved / (the clip's own stride speed x the body's scale)

The feet stay planted at every speed, including:
    - accelerating and braking (the giants' heavy inertia)
    - heat-slowed, cold-tired or sneaking
    - pushed by the AI

Footprints and step sounds happen at the moment each foot really touches down, where it
lands.

The speeds below are then chosen so every gait plays close to a natural cadence (the
playback rate = speed / (stride x scale)).

STRIDE / CONTACT / BUILT-IN SLIP numbers are measured from UAL1_Standard.glb.
tools_pass52_check.py measures them again from the file, so a new animation file can't
silently break them.
"""
from __future__ import annotations

import math

# Natural ground speed of each in-place clip, metres per second at scale 1.0 and playback 1.0:
# the speed of the planted forefoot (ball joint) during contact.
CLIP_STRIDE = {
    'Walk_Loop': 0.98,
    'Walk_Formal_Loop': 0.98,
    'Jog_Fwd_Loop': 5.92,
    'Sprint_Loop': 8.98,
    'Crouch_Fwd_Loop': 0.72,
}
# How unevenly each clip sweeps its planted foot: the slip that remains even at the perfect
# speed (it is in the animation itself). The crouch-walk was animated with a real slide in it.
CLIP_BUILT_IN_SLIP = {
    'Walk_Loop': 0.09,
    'Walk_Formal_Loop': 0.09,
    'Jog_Fwd_Loop': 0.02,
    'Sprint_Loop': 0.03,
    'Crouch_Fwd_Loop': 0.53,
}
# When each foot touches down, as a fraction of the cycle (left, right).
CLIP_CONTACTS = {
    'Walk_Loop': (0.963, 0.463),
    'Walk_Formal_Loop': (0.963, 0.463),
    'Jog_Fwd_Loop': (0.009, 0.509),
    'Sprint_Loop': (0.0, 0.5),
    'Crouch_Fwd_Loop': (0.954, 0.475),
}

GIANT_SCALE = 11.0
HUMAN_SCALE = 1.0

# gait -> (clip, ground speed m/s)
#   human: Pass 58 - quicker on foot (+21-27%; the giants are unchanged). Rates:
#          walk 1.48   jog 0.95   sprint 0.94   crouch 1.32   (cadence 2.2 / 2.0 / 2.8 / 1.4 steps per s)
#          (a walk much above 1.5x its clip's pace looks frantic, so the walk stops at 1.45 m/s)
#          The walk cycle still follows the ground covered, so the feet stay planted.
#   giant: every gait on the walk cycle - a 20 m body stays grounded and heavy, never airborne:
#          rates  walk 0.34 (a step every 2.0 s)   jog 0.63 (1.1 s)   sprint 0.88 (0.8 s)
#          The giants' speeds are the same as before Pass 52, so the world's distances and
#          the Red Giant's balance are unchanged.
GAITS = {
    'human': {
        'walk': ('Walk_Loop', 1.45),           # Pass 58 (was 1.20)
        'jog': ('Jog_Fwd_Loop', 5.60),         # (was 4.40)
        'sprint': ('Sprint_Loop', 8.40),       # (was 6.60)
        'crouch': ('Crouch_Fwd_Loop', 0.95),   # (was 0.85; its clip slides, so only a little quicker)
    },
    'giant': {
        'walk': ('Walk_Loop', 1.35 * math.sqrt(GIANT_SCALE) * 0.82),     # 3.67 m/s
        'jog': ('Walk_Loop', 2.50 * math.sqrt(GIANT_SCALE) * 0.82),      # 6.80 m/s
        'sprint': ('Walk_Loop', 3.50 * math.sqrt(GIANT_SCALE) * 0.82),   # 9.52 m/s
        'crouch': ('Crouch_Fwd_Loop', 1.15 * math.sqrt(GIANT_SCALE) * 0.82),
    },
}
MAX_PHASE_STEP = 0.45            # never skip more than ~a step in one frame (a teleport is not a stride)


def gait(body: str, name: str):
    """(clip, speed) for a body ('human' or 'giant') and a gait."""
    table = GAITS[body]
    return table.get(name, table['walk'])


def speed(body: str, name: str) -> float:
    return gait(body, name)[1]


def playback_rate(clip: str, ground_speed: float, scale: float) -> float:
    """How fast the clip plays at this ground speed (1.0 = as authored)."""
    return ground_speed / (CLIP_STRIDE[clip] * scale)


def phase_advance(clip: str, duration: float, distance: float, scale: float) -> float:
    """Fraction of the cycle covered by moving `distance` metres with this clip."""
    if distance <= 0.0:
        return 0.0
    seconds = distance / (CLIP_STRIDE[clip] * scale)
    return min(MAX_PHASE_STEP, seconds / duration)


def contacts_crossed(clip: str, phase0: float, phase1: float):
    """Feet that touched down between phase0 and phase1 (phase1 may pass 1.0):
    [(side, phase_at_touchdown), ...] in order."""
    left, right = CLIP_CONTACTS.get(clip, (0.0, 0.5))
    hits = []
    base = math.floor(phase0)
    for k in (base, base + 1):
        for side, c in (('left', left), ('right', right)):
            p = k + c
            if phase0 < p <= phase1:
                hits.append((p, side))
    hits.sort()
    return [(side, p % 1.0) for p, side in hits]


# ---------------------------------------------------------------- measuring (for the check)
def measure_clip(glb_path, clip: str, hz: int = 240):
    """Measured from the animation file:
    (stride speed m/s, (left touchdown, right touchdown), built-in slip).

    stride     = median speed of the planted forefoot (ball joint within 1.2 cm of its lowest).
    built-in   = how unevenly the animator swept that foot: the slip even a perfect speed leaves.
    """
    import numpy as np
    from gltf_idle import GLBIdleSkin

    skin = GLBIdleSkin(glb_path, clip)
    n = int(skin.duration * hz)
    ts = np.linspace(0, skin.duration, n, endpoint=False)
    pts = np.array([skin._skin_and_node_points(t, wrap=False)[1] for t in ts])
    vels, touch = [], []
    for ball, heel in (('ball_l', 'foot_l'), ('ball_r', 'foot_r')):
        b = pts[:, skin.node_index[ball]]
        h = pts[:, skin.node_index[heel], 1]
        y, z = b[:, 1], b[:, 2]                               # glTF: y up, z forward
        v = -np.gradient(z, 1.0 / hz)
        vels.append(v[y <= y.min() + 0.012])
        clear = np.minimum(y - y.min(), h - h.min()) <= 0.02
        downs = [i for i in range(n) if clear[i] and not clear[i - 1]]
        # the touchdown that starts the longest contact (ignores small bounces)
        best = max(downs, key=lambda i: next((k for k in range(n) if not clear[(i + k) % n]), n)) if downs else 0
        touch.append(best / n)
    allv = np.concatenate(vels)
    stride = float(np.median(allv))
    built_in = float(np.mean(np.abs(allv - stride)) / stride)
    return stride, (touch[0], touch[1]), built_in
