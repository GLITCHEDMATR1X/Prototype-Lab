# Vector Wars Pass 20 — Startup Render Regression Repair

STATUS: CANDIDATE — target Windows visual confirmation required

## Trigger
Player screenshot showed a live Vector Wars window with a black client area and undefined white geometry, with no normal HUD visible.

## Root-cause reasoning
The gameplay HUD is unconditionally drawn before each completed presented frame. A window with no HUD therefore indicates that the OS window became visible before Vector Wars had presented its first valid gameplay frame. Pygame only makes display changes visible after display.flip()/update(), and long setup work should continue servicing the event system.

## Fix
- Added `_present_startup_frame()` immediately after final startup window sizing/maximize resolution.
- Explicitly fills the display black, renders VECTOR WARS + startup status + exact version, flips the display, and pumps events.
- Updates startup status once city/combat systems begin construction.
- Updated APP_VERSION to `0.9.0-pass20-startup-render-repair` so screenshots identify the exact running branch.
- No combat, progression, save, audio, HoloVerse contract, balancing, or HUD gameplay logic changed.

## Regression gate
27/27 PASS including new Pass 20 startup-render contract.

## Reference check
- pygame-ce display documentation: display content requires flip/update to become visible.
- pygame-ce event documentation: event processing/pump is required so the window can respond to the OS during long-running work.
- Player screenshot supplied 2026-09-20: direct evidence of the startup visual regression.

## Acceptance boundary
Container still lacks pygame-ce runtime, so Windows visual confirmation of the repaired startup frame is required before this candidate is accepted.
