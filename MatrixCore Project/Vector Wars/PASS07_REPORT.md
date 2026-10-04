# Vector Wars Pass 07 — Ground Kill Attribution Repair

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce unavailable in container)

## Task
Repair the Ground-operation regression found while rechecking Pass 06 before starting the Air loop.

## Fixed
- Player bullet destruction of a street vehicle now records `GROUND / STREET`.
- Player missile destruction of a Giant now records `GROUND / GIANT`.
- Existing bullet-vs-Giant and missile-vs-street classifications remain correct.

## Why this blocks progression work
Pass 04 requires eight street-unit kills followed by one Giant kill. Misclassifying these targets can complete the wrong stage and invalidate the campaign progression state, so the accepted Ground loop must be repaired before Air receives new mission logic.

## Scope frozen
No Air mission changes, Ocean changes, visual changes, audio changes, weapon tuning, enemy tuning, or HoloVerse changes.
