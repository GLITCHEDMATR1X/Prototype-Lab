# Vector Wars Pass 04 — Ground Operation Loop

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING (pygame-ce unavailable in this container)
TARGET-RUNTIME TEST: NOT RUN

## Single task
Turn GROUND from an open combat sandbox into the first finite gameplay operation without changing AIR/OCEAN progression or the existing developer front gate.

## Ground operation
1. BREAK STREET ASSAULT — player destroys 8 hostile street units.
2. DESTROY A GIANT — player destroys 1 Giant mech.
3. GROUND SECURED — Ground outcome becomes COMPLETE and the current vehicle receives one full hull/shield repair-resupply.

Relevant player kills are remembered even if completed out of order. Death/redeploy does not yet reset mission progress; failure/checkpoint behavior remains a later dedicated pass.

## Frozen
AIR loop, OCEAN loop, automatic front transitions, save/progression, music, enemy balancing, renderer, vehicle controls, F4 developer gate.

## Source reference
pygame-ce's timing documentation defines Clock.tick/get_time as frame elapsed-time tools. The existing game already uses its per-frame `dt`; Pass 04 does not add an independent timer or blocking wait. This keeps the operation state deterministic and frame-rate independent.
https://pyga.me/docs/ref/time.html

## Verification boundary
Pure-Python operation/outcome tests and static integration contracts are run. Native Pygame rendering remains pending because pygame-ce 2.5.7 is unavailable in this container.
