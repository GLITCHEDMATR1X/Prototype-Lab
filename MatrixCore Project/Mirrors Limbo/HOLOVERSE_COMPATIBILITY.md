# Mirror's Limbo — HoloVerse native linked-reality contract

Pass 84 preserves the same-window native architecture and hardens lifecycle ownership.

## Stable responder

HoloVerse should inspect:

`holoverse/holoverse_dimension.json`

Authority:

- id: `mirrors_limbo`
- protocol: `holoverse_responder_v1`
- entry: `main.py`
- engine: `panda3d`
- compatibility: `native`
- native adapter: `holoverse_native_adapter.py`
- host contract: `holoverse_dimension_v1`
- return target: `gleebs_dimension_archive`

The root `dimension.json` remains supplemental cross-version metadata.

## Native ownership

- HoloVerse owns ShowBase, the OS window, display region, host camera lifecycle and TAB return.
- Mirror's Limbo does not create another ShowBase, window, subprocess or event loop.
- Embedded Mirror's Limbo skips its private boot splash and does not force splash render frames into the HoloVerse window.
- Mirror-owned audio, tasks, Messenger bindings, UI and scene branches are cleaned on return.
- Any HoloVerse AudioManager concurrent-sound limit temporarily changed by the dimension is restored on exit.
- ESC remains local/return-safe and never kills the borrowed host.

## Link/relink

Link by selecting the actual `Mirrors Limbo/main.py` through HoloVerse's LINK SIMULATION control.

Pass 75 was packaged under `Mirrors Limbo Pass75 DistortedCourtyard/`; Pass 76 and later use the stable root `Mirrors Limbo/`. A link stored against the old Pass 75 path therefore needs one manual relink. After that, keep replacing the contents of the stable `Mirrors Limbo/` directory in-place.

No `.holoverse_link.json` or UUID is fabricated in this build.
