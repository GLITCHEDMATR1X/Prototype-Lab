# Vector Wars Pass 12 — Three-Front Campaign Completion + Replay

## Status
CANDIDATE — source/regression accepted; native pygame-ce visual runtime remains pending in this container.

## Single task
Give the existing Ground -> Air -> Ocean campaign a real terminal state and deliberate replay loop after Ocean completion.

## Changes
- PhaseProgression now owns one-way campaign completion from OCEAN.
- Ocean completion commits the campaign exactly once.
- Completed campaign freezes simulation time using the same frame-freeze principle already used by the quit modal.
- Mouse fire is released and normal gameplay keyboard input is swallowed while complete.
- HUD objective becomes `CAMPAIGN COMPLETE // ENTER TO REPLAY`.
- Center-screen victory treatment states all three fronts are secured.
- ENTER/KP ENTER restarts the exact script/executable in a fresh process so destroyed city/enemy/projectile/runtime state cannot leak into a replay.
- ESC remains the deliberate quit/HoloVerse-return path.
- No new combat systems, enemies, weapons, phase objectives, audio tracks, or balance changes.

## Validation
- Previous Pass 11 regression authority: 13/13 PASS before editing.
- Expanded Pass 12 regression authority: 14/14 PASS.
- `python -m py_compile`: PASS.
- Fresh extracted package regression replay: required before delivery.

## Visual acceptance boundary
pygame-ce is still unavailable in this execution container. The victory treatment was checked structurally for centered layout and text footprint, but native rendered visual acceptance remains PENDING.
