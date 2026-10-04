# Operation StarFall Pass99 — Modal Authority

Base: Pass98 Operation Transition Isolation Fix.
Primary target: embedded moon options modal ownership/readability.
Frozen system: Pass98 operation-transition isolation and camera/post-FX cleanup.

## Reproduced defect
In the actual Panda3D frame, opening Mimas options left shell operation HUD, sonar/vision UI, crosshair and mission prompts visible behind the options modal. At 1280x720 the options text was also too small and the repeated `MAP` controls were difficult to read.

## Repair
- Snapshot and suppress normal operation UI while the options modal is open.
- Restore exactly the previously-visible operation UI when the modal closes.
- Do not restore operation HUD during TAB teardown/return.
- Added runtime `options_modal_is_exclusive()` regression probe.
- Extended the existing return-controls self-test to prove modal exclusivity, close restoration, reopen exclusivity, TAB return, and zero embedded residue.
- Reduced options copy, increased modal opacity/text size, and changed remap controls from identical `MAP` labels to action + current-key labels.

## Runtime evidence
Panda3D 1.10.16 / Python 3.13.5, Linux offscreen renderer.
- 1280x720 modal frame visually inspected: PASS.
- 1920x1080 modal frame visually inspected: PASS.
- Mimas options open/close/reopen/TAB return regression: PASS.
- Mimas -> ship -> Enceladus -> ship transition cycle: PASS.
- Cleanup residue after return: 0 render roots / 0 UI roots.

Packaging gate: clean ZIP, fresh extraction, compile, package hygiene, and the critical Mimas options/return runtime were all reproduced from the packaged copy. Windows/native-GPU player validation remains pending. Status is CANDIDATE, not accepted authority.
