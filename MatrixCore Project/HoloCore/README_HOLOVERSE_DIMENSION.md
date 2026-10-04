# HoloCore — External HoloVerse Dimension

HoloCore is a standalone Panda3D project and a native HoloVerse dimension.

Expected location:

```text
Prototype Lab/
  HoloVerse/
  MatrixCore Project/
    HoloCore/
      main.py
      holoverse_native_adapter.py
      holoverse/holoverse_dimension.json
```

For normal player flow, launch HoloVerse first and enter HoloCore from Gleebs'
Dimension Archive. HoloVerse loads `holoverse_native_adapter.py` into its existing
Panda3D process/window. HoloCore owns its scene and local controls; HoloVerse owns
TAB and restores itself on return.

For standalone HoloCore development, run `main.py` directly. The standalone game
does not need HoloVerse to exist.

The adapter must not import a second ShowBase, open a second window, or depend on
a HoloCore implementation inside HoloVerse.

## The world: an ocean without water (Pass HC-1)

The neon grid is the seabed. Above it there is no surface and no ceiling, only an open column that goes up forever. The seabed looks exactly as it always has, and the creatures are unchanged. Everything HC-1 adds starts above the seabed.

The column is split into **strata**, which are altitude bands read from `assets/strata/strata.json`:

| Band | From | Life | Drop-in assets |
|---|---|---|---|
| Seabed Grid | the floor | the seabed's own creatures and flora, unchanged | `assets/biome*/` |
| Drift Column | 180 m | jellyfish, a few mermaids | plankton bloom, drifting signal kelp |
| Lantern Shoals | 760 m | mermaids, jellyfish | lantern orbs |
| Leviathan Reach | 1560 m | big octopuses, jellyfish | leviathan ribcages |
| Open Void | 2640 m, open-ended | sparse jellyfish | reserved for the next biome |

Above the seabed:
- The background and fog shift gently by band and blend across each band floor, so there is no horizon line.
- Drifting specks ("marine snow") make height and motion readable in the empty water.
- A faint ring marks a band floor just before you reach it, and the band's name shows briefly when you cross.
- Creatures up here are the same jellyfish, mermaid and octopus models, drifting free instead of following the seabed. Far ones are drawn as a frozen, flattened copy to keep frame times down.

**Controls**

| Mode | Keys |
|---|---|
| On foot | WASD move, Shift sprint, mouse look, Space / Page Up rise, C / Page Down sink. Height above the seabed is kept while you walk. |
| Vessel pilot | W/S thrust, A/D yaw, Space/C climb or descend, **Shift boost** (×2.6 climb, ×2 thrust). |
| Leaving the vessel | Parked or hovering low, you step down onto the seabed. Higher up, you float out beside it. |

**Adding an upward biome**
1. Append a band to `strata.json` with a higher `floor`, its colours, `creatures` densities and an `asset_folder`.
2. Drop `*.py` assets into `assets/strata/<asset_folder>/`. Each one needs a `STRATA_OBJECT` dict and a `build(parent, x, y, z, rng, metadata)` function, and can have an `update(node, time)` function. See `assets/strata/open_void/README.md`.

**Checks**
- `python tools/validate_holocore_hc1.py`: offscreen.
- `python tools/smoke_holocore_strata.py`: windowed. Visits every band and writes screenshots and a report to `logs/`.
