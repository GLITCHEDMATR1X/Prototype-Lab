# HoloVerse // MatrixCore Observatory

## Where your saves go

HoloVerse never writes into its own game folder. Settings, progression, region saves,
the Dimension Archive and logs are kept per player in:

- Windows: `%LOCALAPPDATA%\GLITCHED MATRIX\HoloVerse\`
- macOS: `~/Library/Application Support/GLITCHED MATRIX/HoloVerse/`
- Linux: `~/.local/share/glitched-matrix/holoverse/`

Inside: `dimension_archive.json`, `saves\` (settings and progress) and `logs\`.
Delete that folder to start completely fresh. Other Glitched Matrix games keep their
own folders beside it (for example `GLITCHED MATRIX\INDIGO GIANT`).

---

# HoloVerse Pass 282.49 — Main Loop Cadence

Pass 282.49 builds directly on Pass 282.48. It preserves the wider Observatory, per-reality planet identities, Pass 282.46 distance LOD, Pass 282.45 tree authority, the short-range ground-artifact focus contract, dimension routes, audio, controls, and saved state while removing two remaining pieces of unnecessary foreground work from normal gameplay.

## Changes

- Campaign synchronization no longer runs from the per-frame `update_task` path.
- Campaign progress now uses Panda3D's delayed-task queue at a 0.75 second cadence.
- Regional campaign JSON files are cached by `(mtime_ns, size)` and are parsed only when a file actually changes.
- Unchanged campaign heartbeats perform metadata checks only and no repeated JSON decoding.
- The active campaign state remains in memory between writes instead of rereading `campaign_state.json` every heartbeat.
- The authoritative `main.py` HUD now uses the accepted 10 Hz automatic refresh cadence already used by the fallback world runtime.
- Explicit interactions, menus, settings, state changes, and forced refreshes remain immediate.
- No world geometry, trees, Observatory spacing, planet identity, artifact range, launch routing, controls, or save schema changed.

## Performance finding

Pass 282.48 removed the expensive 2-second Dimension Registry filesystem scan. The remaining main loop still performed campaign JSON polling every 0.75 seconds and called the main HUD rebuild once per rendered frame. Panda3D documents `doMethodLater()` as the more efficient way to schedule delayed work, and frequent text regeneration is avoidable when the displayed information does not need frame-rate updates.

In the Pass 282.49 deterministic cadence smoke, 40 unchanged campaign heartbeats perform zero JSON reads after the initial cache fill. A changed regional state causes only that one JSON file to be parsed and still advances the campaign normally. Simulating 600 frames at 60 Hz reduces automatic main-HUD refresh calls from 600 to about 100 while explicit forced refresh remains immediate.

## Controls

Controls are unchanged from Pass 282.48. Ground artifacts/HoloForge still require nearby deliberate focus before E. Observatory planets retain Mouse1 entry/link behavior. TAB remains the universal HoloVerse return key for active native dimensions.
