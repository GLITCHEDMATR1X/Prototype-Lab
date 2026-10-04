# Pass 59 Report — AR Coverage Continuity + Tree Removal

## Goal
Continue the GXT.6 AR coverage audit after Pass 58 and remove the tree presentation the user no longer wants.

## Findings
The Pass 58 annex repair held. A wider full-screen AR sweep then exposed another continuity issue: the 24 boulevard `promenade_node` pads were untextured solid boxes. At close range one could fill a large portion of the screen as a blank muted rectangle while the surrounding pavement was richly patterned. Physical park slabs also sat higher than the broad district ground field, creating another potential AR surface mismatch.

## Changes
- Removed city tree generation.
- Removed exterior tree generation.
- Removed tree trunk collision and projected tree-shadow sources by eliminating those runtime objects.
- Preserved low park slabs in physical reality.
- Added eight same-footprint district-textured AR park surfaces.
- Converted all 24 promenade node pads to district-textured pavement.
- Added `--ar-coverage-smoke`.

## Acceptance targets
- 8/8 physical parks hidden from the AR camera.
- 8/8 AR park surfaces registered.
- 24/24 boulevard node pads textured.
- Zero tree geometry at runtime.
- Zero tree shadow sources.
- Pass 58 annex coverage, Pass 57 traversal and Pass 56 surface winding preserved.

## GXT.6 / runtime validation
- Pass 58 recheck before editing: surface, traversal, residents and main smoke PASS.
- GXT.6 wider AR inspection plus direct runtime examination identified the flat boulevard node pads. The generic screenshot heuristic scored the before/after frames similarly, so semantic material-continuity detection remains a useful future GXTool/Astra improvement.
- `AR_COVERAGE_SMOKE_PASS`: 8/8 parks covered in AR, 24/24 node pads textured, trees removed.
- `TRAVERSAL_SMOKE_PASS`: 8/8 avenues, 4/4 gates, south entrance clear, no collision-pusher correction.
- `SURFACE_SMOKE_PASS`: top-face winding preserved.
- `RESIDENT_SMOKE_PASS`: two residents synchronized; deterministic bone-following AR designs preserved.
- `INTERIORS_SMOKE_PASS`: all five interiors remain traversable; Pass 58 annex coverage preserved.
- `SHADOW_SMOKE_PASS`: buildings/walls/bridges/Gleebs remain grounded; tree shadow sources are zero.
- `GLEEBS_BEHAVIOR_SMOKE_PASS`: approach/wave/idle/head follow preserved.
- `AR_OPTIMIZATION_SMOKE_PASS`: 5716 pre-optimization nodes -> 1247 post-optimization nodes.
- `VIEWPORT_SMOKE_PASS`: 1920x1080 / 16:9 aligned.
- `UTOPIA_SYSTEMS_SMOKE_PASS`: all five Utopia systems preserved.
- Static validation: 317/317 PASS.
- Asset audit: PASS.
- GXT.6 full-pass: deliverable / 0 blockers. Generic asset-reference and long-text warnings remain non-blocking scanner limitations; the project-specific asset audit resolves the actual files successfully.

Status: CANDIDATE pending Windows player-facing acceptance.
