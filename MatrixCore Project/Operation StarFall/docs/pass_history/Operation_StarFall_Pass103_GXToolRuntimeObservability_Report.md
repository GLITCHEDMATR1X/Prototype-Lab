# Operation StarFall Pass103 — GXTool Runtime Observability

## Primary target
Make the current StarFall shell directly inspectable by GXTool v4 without changing normal player startup or adding a runtime dependency on GXTool.

## What GXTool found
The initial static host-ownership warnings were investigated with bounded source inspection and were mostly explicit QA/self-test exits, so they were not patched. The decisive finding was that `panda3d-runtime-inspect` could launch Pass102 but could not obtain semantic runtime proof. After the optional GXTool hook was added, deterministic runtime capture exposed the actual startup interior rather than a curated screenshot.

That proof revealed two startup-authority defects: the interior-first spawn faced the rear console even though source comments identify the forward viewport as the reason for interior-first play, and exterior presentation lights plus interior section lights were enabled at the global `render` root.

## Changes
- Added an optional GXTool runtime hook that activates only when GXTool requests it.
- Added bounded StarFall semantic state: build, mode, chunk, HUD level, interior heading, operation ownership/residue, and window size.
- Changed the interior spawn heading from rear-facing 0 degrees to forward-facing 180 degrees.
- Scoped exterior ambient/key/rim/fill lights to `flight_root`.
- Scoped the seven authored interior point lights to `interior_root`.
- Did not retune light colors or redesign the interior.

## Frozen systems
Pass102 display authority, Pass101 launch ownership, Pass100 shell ownership, Pass99 modal/return behavior, moon gameplay, operation rewards/results, and the two-operation lifecycle remain frozen.

## Working-tree proof
GXTool deterministic replay at 1920x1080 completed all seven steps with zero assertion failures, including an explicit `interior_heading = 180.0` state assertion and the interior-to-flight toggle. GXTool runtime inspection returned a 1920x1080 interior state with zero operation residue and zero diagnosis warnings/errors. Existing display, shell, launch-authority, Mimas-return, and Mimas->Enceladus lifecycle tests passed after the changes.

## Acceptance boundary
This remains CANDIDATE until the exact packaged copy passes the same gates and the native Windows/player-facing result is accepted. Software-GL/Xvfb output is diagnostic evidence, not a substitute for native-GPU aesthetic acceptance.
