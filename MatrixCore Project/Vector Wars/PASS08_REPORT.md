# Vector Wars Pass 08 — Regression Harness Authority

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce unavailable in container)

## Why this became the pass
Before Air-loop work, the Pass 07 audit found that `python -m unittest discover` reported zero tests even though Vector Wars already had multiple standalone regression scripts. The game branch itself passed those scripts when invoked directly, but there was no single authoritative regression command.

## Single task
Add one deterministic regression entry point that executes every existing Vector Wars regression/contract script from the project root and fails non-zero if any script fails.

## Added
- `tools/run_regressions.py`
- Executes the existing combat-outcome, Ground operation, Ground recovery, Pass 04, Pass 05, Pass 06, Pass 07, and phase-progression checks.
- Prints a concise run/pass/fail summary.
- Returns exit code 1 if any regression script fails.

## Frozen
No gameplay, combat, controls, UI, audio, rendering, progression, or HoloVerse behavior changed.

## Visual boundary
There are no player-facing visual changes in this pass. Native runtime visual acceptance remains pending until pygame-ce can execute in the container.
