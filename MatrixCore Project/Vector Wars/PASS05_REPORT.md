# Vector Wars Pass 05 — Ground Failure + Redeploy

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce 2.5.7 unavailable in container)

## Single task
Replace consequence-free Ground instant respawn with a deliberate failure/redeploy state, without changing Air/Ocean progression.

## Changes
- Ground player destruction enters `REDEPLOY_REQUIRED` exactly once.
- Ground operation progress is preserved.
- ENTER / keypad ENTER redeploys a fresh player unit at the Ground insertion checkpoint.
- Combat outcome authority records the Ground failure and returns to ACTIVE on redeploy.
- Aim input is consumed/frozen during the loss state so mouse drift cannot rotate the next deployment.
- Developer TAB switching is blocked while Ground redeployment is pending.
- Air and Ocean retain their pre-existing immediate replacement behavior until their own phase-loop passes.
- Loss presentation reuses existing HUD regions; no new normal-play panel was added.

## Validation boundary
Pure-Python recovery/state tests, Python compilation, previous Ground-operation regressions, and source contracts pass. Native pygame rendering remains unavailable in this container, so moving visual acceptance is pending.
