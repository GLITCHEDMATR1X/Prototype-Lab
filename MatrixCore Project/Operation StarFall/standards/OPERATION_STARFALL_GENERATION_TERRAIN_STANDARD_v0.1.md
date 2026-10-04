# Operation StarFall — Generation / Rock / Terrain Authority v0.1

## Purpose

Pass44 begins the terrain-authority part of the Mastering / Remastering phase.  Every active moon world must now use explicit generation rules rather than one-off pass hacks.

Active worlds:

- Mimas
- Enceladus
- Iapetus
- Titan

## Core rule

World geometry is generated from deterministic world-space functions.  Terrain-attached objects must snap to sampled terrain, sink their bases into the ground, and remain visual-only unless a later pass deliberately adds collision.

## Required placement rules

| Area | Rule |
|---|---|
| Terrain height | Use `WorldGenerator.surface_height(x, y)` as the authority. |
| Subsurface terrain | Use `WorldGenerator.subsurface_terrain_height(x, y)` where exposed hard terrain is intended. |
| Jagged mountains | Use `_jagged_mountain_patches(x, y)` and world profile strength/density. |
| 3D rocks/spires | Place only from profile-governed candidates. |
| Rock bases | Sink into terrain using `ROCK_BASE_INTERSECT_RATIO`; do not leave daylight gaps. |
| Collision | Rocks are visual-only by default.  No invisible blockers. |
| Titan water | Do not place rock spires in deep methane liquid masks. |
| Identity | Each world keeps its own shape language and color rule. |

## World visual identities

### Enceladus

- Cyan flat sheet ice.
- White/gray buried terrain breaking through the sheet.
- Frosted splinter ridges and ice-rock shards.
- The flat ice plane must remain visually separate from mountain terrain.

### Mimas

- Crater snowpack over ice.
- Named crater basins must align with drill/resource pools.
- Rock forms should be short, battered crater-rim shards.

### Iapetus

- Continuous Cassini Regio / equatorial ridge structure.
- Dark tholin terrain with bright icy caps.
- Rock forms can be taller and more dramatic, but still snap to the ridge terrain.

### Titan

- Methane shoreline, tholin dunes, and underwater blur/depth.
- Rock spires should be warm hydrocarbon/coastal teeth.
- Rocks must avoid deep liquid masks and stay on terrain/shore.

## Validation

Required tests:

```bash
python -B Worlds/main.py --moon=mimas --generation-authority-test --no-audio
python -B Worlds/main.py --moon=enceladus --generation-authority-test --no-audio
python -B Worlds/main.py --moon=iapetus --generation-authority-test --no-audio
python -B Worlds/main.py --moon=titan --generation-authority-test --no-audio
python -B Worlds/main.py --moon=titan --pass37-rocks-underwater-test --no-audio
python -B Worlds/main.py --moon=titan --placement-authority-test --no-audio
```

Reject a generation pass if:

- rocks are placed with hardcoded one-off rules outside the world profiles
- visual rocks create movement blockers
- terrain props float above the ground
- Titan rocks spawn in deep methane
- a visual feature ignores the all-world screen/action/progress/audio contracts
