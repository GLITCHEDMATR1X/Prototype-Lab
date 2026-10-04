# Mirror's Limbo Pass 84 — HoloVerse reconnect diagnostic

## What actually changed

The HoloVerse responder/adapter files in Pass 83 were byte-for-byte identical to the older user-supplied build that had previously linked successfully. The most concrete continuity break is the project directory itself:

- Pass 75 ZIP root: `Mirrors Limbo Pass75 DistortedCourtyard/`
- Pass 76+ ZIP root: `Mirrors Limbo/`

HoloVerse stores the selected `main.py` path for manually linked simulations. If the old link still points at the Pass 75 directory, the file has moved and HoloVerse cannot follow that stale path automatically.

## Pass 84 hardening

Pass 84 keeps the package root permanently stable as `Mirrors Limbo/` and strengthens the native responder:

- responder ID: `mirrors_limbo`
- protocol: `holoverse_responder_v1`
- compatibility: `native`
- adapter: `holoverse_native_adapter.py`
- factories: `create_mode`, `create_native_mode`, `create_native_adapter`, `create_adapter`
- embedded source import explicitly marks `HOLOVERSE_EMBEDDED_MODE=1`
- Mirror's Limbo does not create/show its standalone boot splash while hosted
- no forced startup `renderFrame()` calls occur from the dimension while hosted
- TAB remains HoloVerse-owned
- the HoloVerse audio manager's previous concurrent-sound limit is restored on exit
- no `.holoverse_link.json` or fabricated UUID is shipped, avoiding duplicate linked-reality identities

## One-time recovery if the old path is stale

Use HoloVerse's **LINK SIMULATION** once and select the new stable path:

`Mirrors Limbo/main.py`

After that, replace future builds in-place under the same `Mirrors Limbo/` folder instead of extracting each pass under a different pass-numbered directory. The persistent link path will then remain valid.
