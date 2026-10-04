# Operation StarFall Pass101 — Operation Launch Authority

Base: Pass100 Shell Panel Authority Candidate.
Primary target: shared operation loading/handoff authority and loading-screen consistency.
Frozen systems: Pass100 shell panels, Pass99 embedded options ownership, moon-world gameplay, operation result/credit flow, return lifecycle.

## Previous-pass recheck
- Pass100 shell UI authority: PASS.
- Pass99 Mimas options open/close/reopen/TAB return: PASS.
- Mimas -> ship -> Enceladus -> ship cycle: PASS.
- Embedded cleanup residue after return: 0 render roots / 0 UI roots.

## Reproduced defects
- Two `begin_operation_loading()` calls inside the 1.1-second loading window queued two `finish_operation_loading` tasks.
- The second request replaced `pending_operation_code`, so rapid repeated input could retarget the operation before handoff.
- `start_embedded_world_operation()` had no independent active-operation guard, leaving a stale duplicate finish task capable of constructing another embedded app into the same ShowBase.
- Europa's destination loading art was a live-looking gameplay/terrain screenshot with HUD text baked into the image while the other seven destinations used clean cinematic planet cards.

## Repair
- Added explicit `operation_loading_in_progress` ownership.
- Duplicate launch requests during loading now leave the first destination and loading root unchanged.
- A defensive task cleanup ensures only one `finish_operation_loading` task is scheduled.
- `_finish_operation_loading()` refuses stale work once an operation is active and ignores work when no launch owns the transition.
- `start_embedded_world_operation()` now rejects construction if an embedded operation is already active.
- Failed launches clear loading/pending state and remove the loading layer instead of leaving stale transition state.
- Added `--operation-launch-authority-test` covering duplicate input, one-app/one-root construction, cleanup, and deliberate failed-launch recovery.
- Replaced Europa's leaked gameplay loading image with a clean 1920x1080 cinematic Europa card built from the existing Europa boot-view asset.

## Runtime evidence before packaging
Panda3D 1.10.16 / Python 3.13.5, Linux offscreen runtime.
- Duplicate-launch authority regression: PASS.
- Deliberate failed-launch recovery: PASS.
- Europa loading screen at exact 1280x720: visually inspected, PASS.
- Pass100 shell authority regression: PASS.
- Pass99 Mimas return-controls regression: PASS.
- Mimas -> Enceladus cycle: PASS.

Preverification package gate: clean ZIP -> blank extraction -> compile -> package hygiene -> launch-authority test -> Europa 720p capture -> shell authority -> Mimas return controls -> Mimas/Enceladus cycle -> post-runtime hygiene all passed. The exact final archive was then blank-extracted and the critical runtime/package gates were repeated before delivery.
Windows/native-GPU player validation remains pending. Status is CANDIDATE, not accepted authority.
