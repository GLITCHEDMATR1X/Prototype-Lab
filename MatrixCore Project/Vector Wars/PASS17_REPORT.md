# Vector Wars Pass 17 — Phase Pacing Authority

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce 2.5.7 unavailable in this container)

## Single task
Separate player traversal pacing by combat phase so Ground and Ocean no longer inherit fighter-like movement scale.

## Changes
- Added `pacing_balance.py` as the single phase-pacing authority.
- AIR keeps the existing full player speed scale (`1.00`).
- GROUND now uses a compressed player speed scale (`0.48`) so street/mech combat reads as ground-scale traversal instead of fighter-scale traversal.
- OCEAN generic ship acceleration uses a lower scale (`0.66`) and the speedboat cruise model now tops out at 126 game units under full throttle + boost instead of the previous 170-like fighter-scale value.
- Ocean cruise authority is centralized rather than embedded as magic numbers in `main.py`.
- No weapon damage, reload, mission counts, enemy populations, HUD, audio, save, or progression logic changed.

## Reference basis
These are gameplay ratios, not literal unit conversions.

Primary-source anchors:
- National Museum of the U.S. Air Force lists the F-16A maximum speed at 1,345 mph.
- U.S. Navy DDG-51 fact file lists Arleigh Burke-class destroyer speed as in excess of 30 knots.
- U.S. Navy MH-60 fact file lists maximum airspeed at 180 knots.

The real-world difference is much larger than Vector Wars uses. Pass 17 deliberately compresses it so each phase remains playable while still restoring clear movement identity.

## Regression result
`python tools/run_regressions.py`

23/23 PASS.

## Verification boundary
The container still cannot import/run pygame-ce 2.5.7, so motion feel and visual acceptance remain pending. This pass has source/math/regression authority only; it is not claimed as runtime accepted.
