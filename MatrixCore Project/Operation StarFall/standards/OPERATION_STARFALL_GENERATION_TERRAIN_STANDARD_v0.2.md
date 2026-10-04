# Operation StarFall — Generation / Rock / Terrain Authority v0.2

## Purpose

Pass104 extends terrain authority to every active StarFall surface and closes the finite-heightfield presentation gap. Gameplay bounds remain finite and deterministic, but the player must not see a square terrain mesh end in open space.

Active worlds:

- Mimas
- Enceladus
- Iapetus
- Titan
- Mars
- Pluto
- Europa
- Triton

## Core terrain rule

World geometry is generated from deterministic world-space functions. Terrain-attached objects use the same sampled height authority as player movement. Visible terrain must remain continuous through the edge of the playable region.

`WORLD_HALF` is a gameplay/simulation boundary. It is **not** allowed to read as the visual end of a planet.

## Horizon authority

For Mimas, Enceladus, Titan, Mars, Pluto, Europa and Triton:

- the original playable heightfield remains unchanged inside `WORLD_HALF`;
- a visual-only continuation ring begins at exactly `WORLD_HALF`;
- ring band zero samples the same `WorldGenerator.surface_height(x, y)` authority as the playable terrain;
- perimeter segmentation matches the playable heightfield edge grid to avoid T-junction cracks;
- terrain continues several kilometers beyond the movement boundary;
- the far ring descends gradually into atmospheric/fog depth instead of ending as a vertical cliff or empty square;
- the continuation has no collision and never expands gameplay bounds.

Titan additionally continues the methane liquid mask and shoreline sheen beyond `WORLD_HALF`, fading the transparent liquid toward the distant ring edge.

Iapetus is intentionally different. Its existing circular play radius and `_iapetus_void_factor_at()` horizon fade must hide the square mesh edge before it becomes visible; do not layer the generic continuation over that authored globe-slice illusion.

## Required placement rules

| Area | Rule |
|---|---|
| Terrain height | Use `WorldGenerator.surface_height(x, y)` as gameplay/top-surface authority. |
| Subsurface terrain | Use `WorldGenerator.subsurface_terrain_height(x, y)` where exposed hard terrain is intended. |
| Jagged mountains | Use `_jagged_mountain_patches(x, y)` and world profile strength/density. |
| 3D rocks/spires | Place only from profile-governed candidates. |
| Rock bases | Sink into terrain using `ROCK_BASE_INTERSECT_RATIO`; do not leave daylight gaps. |
| Collision | Rocks and horizon continuation are visual-only by default. No invisible blockers. |
| Titan liquid | Do not place rock spires in deep methane liquid masks. |
| Terrain edge | The playable square may constrain movement, but its edge may never be the visible end of terrain. |
| Identity | Each world keeps its own shape language, palette and special terrain rules. |

## World visual identities

### Enceladus

- Cyan flat sheet ice.
- White/gray buried terrain breaking through the sheet.
- Frosted splinter ridges and ice-rock shards.
- The flat ice plane remains visually separate from exposed mountain terrain.

### Mimas

- Crater snowpack over ice.
- Named crater basins align with drill/resource pools.
- Short battered crater-rim shards.

### Iapetus

- Continuous Cassini Regio / equatorial ridge structure.
- Dark tholin terrain with bright icy caps.
- Existing circular horizon fade owns edge concealment.

### Titan

- Methane shoreline, tholin dunes and underwater depth.
- Warm hydrocarbon/coastal teeth.
- Terrain, methane and shoreline masks remain continuous beyond the playable edge.

### Mars

- Dry rust channels and frost/snow-cap zones.
- No inherited visible liquid plane.
- Wind-cut shelves remain part of one continuous dry surface.

### Pluto

- Sputnik Planitia nitrogen plain bordered by water-ice mountains and dark uplands.
- The generated playable heightfield is the visible surface authority; no inherited flat sheet may cover basin terrain.

### Europa

- White ice canyon, dark wall faces and narrow iron-red crevices.
- Canyon shoulders and fracture gouges stay continuous in world coordinates and do not terminate at the play boundary.

### Triton

- Long nitrogen-frost valley networks beneath close Neptune.
- Broken shelves and ridge walls remain continuous through the playable edge.

## Validation

Primary runtime proof for a terrain pass is the failure-revealing edge view:

```bash
python -B Worlds/main.py --moon=<world> --test-shot <output.png> --terrain-horizon-shot --no-audio
```

Run it for all eight worlds. For Mimas/Enceladus/Mars/Pluto/Europa/Triton/Titan the shot must show natural continuation beyond the movement boundary. Iapetus must show its existing authored horizon fade with no visible square edge.

Also run the generation authority contract for each world:

```bash
python -B Worlds/main.py --moon=<world> --generation-authority-test --no-audio
```

Reject the pass if:

- a square terrain edge or void is visible from the edge-QA view;
- continuation begins above/below the playable edge and creates a seam;
- Titan methane stops at the old terrain boundary;
- continuation gains collision or changes movement bounds;
- terrain props float or visibly disconnect from their sampled surface;
- Iapetus' authored circular horizon treatment is damaged;
- the exact Panda3D runtime cannot be exercised and the pass is described as visually accepted anyway.
