# Vector Wars Pass 03 — Combat Outcome Authority

**Status:** CANDIDATE  
**Visual acceptance:** PENDING  
**Target runtime:** NOT RUN — pygame-ce 2.5.7 is unavailable inside this container.

## Single task

Create deterministic outcome authority for the three existing combat fronts without changing how the player moves between them.

## Result

Each front now has `ACTIVE`, `COMPLETE`, and `FAILED` state. Player-attributed hostile destructions advance a bounded objective counter. Ground completes at 12, Air at 8, and Ocean at 4. These are prototype gameplay quotas, not claims about real-world military doctrine; later pacing passes may tune them after runtime testing.

Player destruction records a failed attempt before the existing immediate respawn. Respawn starts another active attempt unless the front was already complete. Completion is sticky. No code in this pass automatically switches fronts.

## UI containment

Outcome state is visible only when F3 diagnostics are enabled. Normal gameplay receives no new permanent panel. This is intentional until the actual progression loop is accepted.

## Verification

The outcome authority was split into `combat_outcomes.py`, which has no Pygame dependency. `tools/test_combat_outcomes.py` verifies initial state, failure, retry, exact completion, capped progress, and non-regression for all three fronts. `main.py` and the new modules compile under Python 3.13.

Fresh renderer screenshots remain blocked by the missing pygame-ce runtime, so this pass is not promoted to ACCEPTED.
