# Operation StarFall Pass112 — Remote Drone Telemetry Authority

Base: Pass111 Interior Authority Recheck Repair Candidate.

## One task

Restore live planet-operation instructions inside the ship's existing 16:9 remote drone display without restoring the hidden planet-local HUD.

## Change

The shell overlay now consumes each embedded world's existing `_standard_action_payload()` and displays its live action hint, state, and progress while retaining rig/sonar telemetry. No planet terrain, display geometry, camera ownership, mission/reward rules, or normal-player flight authority changed.

## Acceptance boundary

GXTOOL/source/regression/package checks are required. Runtime/visual acceptance remains pending until Panda3D 1.10.16 is available in this container; no screenshot is manufactured.

## Workflow correction

During validation, an older Pass110 self-test was briefly executed against the Pass112 tree. Because that historical test writes to a fixed Pass110 report path, it could contaminate frozen evidence. All Pass108–111 contract/hygiene reports were restored from the untouched Pass111 baseline and verified byte-for-byte. Prevention: historical fixed-output self-tests are read as frozen evidence; only the current pass self-test is executed in-place.
