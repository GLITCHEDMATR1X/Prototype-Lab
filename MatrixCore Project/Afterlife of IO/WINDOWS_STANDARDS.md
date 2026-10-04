# Afterlife of IO — Current Windows Runtime Standard

## Display contract

- Logical gameplay canvas: 1280×720, preserved for collision/input compatibility.
- Default bordered window: 1600×900.
- Primary review target: 1920×1080.
- Minimum supported window: 1280×720.
- F11 and Alt+Enter toggle fullscreen at the current desktop resolution.
- Resizing preserves 16:9 presentation and letterboxes rather than stretching artwork.
- Camera bounds must never expose authored PNG edges at supported zoom levels.
- Windows Per-Monitor-V2 DPI awareness is requested before display creation, with a safe fallback.

## Filesystem contract

- Shipped/read-only assets remain relative to `main.py`.
- User saves, settings, and crash diagnostics use `%LOCALAPPDATA%\GLITCHED MATRIX\Afterlife of IO` on Windows.
- The game must not require write permission inside Program Files or a Steam library folder.

## Launch helpers included in this package

- `RUN_GAME.bat`
- `RUN_FULLSCREEN.bat`
- `RUN_DIAGNOSTIC.bat`
- `RUN_RUNTIME_PROBE.bat`
- `RUN_WINDOWS_SMOKE_TEST.bat`
- `INSTALL_DEPENDENCIES.bat`

A Windows executable/build script is not claimed as part of this source package unless it is physically present and separately verified.

## Menu / input acceptance

- Title, Pause, Save/Load, Settings, Settings → Controls, dialogue, Archive, battle, and Inventory must remain usable with keyboard/mouse.
- If a controller is connected, D-pad/analog navigation and A/B-style confirm/back behavior must remain consistent across menu screens.
- Right-stick click opens Inventory during ordinary exploration and retains its Machine Focus flip behavior while Machine Focus is active.
- D-pad Up remains Help.
- Inventory must remain directly reachable with `I` regardless of controller state.
- `Esc` must always provide a reliable back/cancel path from player-facing modal screens.

## Save / quit acceptance

- Three manual save slots remain readable/writable through the pause menu. Current schema is v5 with v4 migration.
- Pause-menu Quit must not exit on the first selection; it must display the explicit confirmation/warning screen.
- Cancel returns to Pause without altering gameplay state.
- Confirm Quit performs a clean shutdown.

## Native Windows acceptance checklist

Before promoting a Windows build, verify:

1. Clean launch at 1920×1080 and fallback 1280×720.
2. Window resize remains 16:9 with no clipped HUD or exposed source-image edges.
3. F11 fullscreen → windowed round-trip.
4. Alt+Tab recovery.
5. High-DPI display scaling at 125%, 150%, and 200%.
6. New Game, Continue, manual Save, and manual Load.
7. `I` Inventory opens/closes and remains readable.
8. Settings → Controls is readable at 1920×1080 and 1280×720.
9. Pause → Quit shows the confirmation screen; Cancel and Confirm both work.
10. Present/Past travel, accepted Present local-route fades, and walk-depth logic remain intact.
11. Controller hot-plug/disconnect does not block keyboard/mouse.
12. Clean exit leaves no unexpected crash log.
