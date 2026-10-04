# Vector Wars Pass 21 — Startup Phase-Order Repair

Status: CANDIDATE — Windows gameplay acceptance pending.

## Trigger
User runtime evidence showed Pass 20 rendered the startup screen, remained on `Preparing city and combat systems...`, then exited before gameplay.

## Root cause
Pass 19 changed normal startup so the saved/campaign-owned phase is restored automatically. If the saved phase is OCEAN, `_apply_combat_mode()` immediately evaluates `ocean_wave_height(..., t_now)`. `t_now` was initialized later in startup, after the restored-phase application. This made the restored Ocean startup path reference the game clock before it had been bound, causing startup to fail before the first gameplay frame.

## Repair
- Move `t_now = 0.0` ahead of campaign restore/application.
- Remove the later duplicate initialization.
- Keep Pass 20's deterministic first-frame/loading presentation intact.
- Add `test_pass21_startup_phase_order.py` so the game clock must remain initialized before restored phase application.
- Update the Pass 20 startup-render regression so it tests behavior rather than hard-coding the old build label.
- No combat, HUD, audio, save schema, pacing, objectives, or HoloVerse behavior changed.

## Regression gate
Source tree: 28/28 PASS.
Fresh-extracted package must reproduce 28/28 before delivery.

## Reference check
Project authority:
- Pass 20 package is REJECTED by actual Windows runtime evidence.
- GLITCHED_MATRIX Prototype Lab Failure Ledger: stop feature work on launch/crash blockers; fix root cause; add regression; fresh-package and retest.

Official reference consulted:
- Python 3.12 Execution Model: a function-scope name used before it is bound can raise `UnboundLocalError`/`NameError` depending on the scope relationship. https://docs.python.org/3.12/reference/executionmodel.html

Project evidence consulted:
- User screenshot of Pass 20 showing the deterministic startup frame stuck at `Preparing city and combat systems...`, followed by process exit.
- Pass 20 and Pass 19 `main.py` startup order.

Known reference conflicts:
- NONE.

Unverified assumptions:
- Native pygame-ce execution remains unavailable in this container, so the repaired saved-Ocean path still requires the user's Windows runtime test.
