# Vector Wars Pass 10 — Air to Maritime Progression

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce unavailable in container)

## Regression gate
Pass 09 authority ran first and passed 10/10. No pre-existing regression blocked this task.

## Single task
Connect successful completion of the Air operation to the existing Ocean combat front without adding the Ocean gameplay loop yet.

## Progression
Normal campaign flow is now:

GROUND COMPLETE
→ AIR PHASE ACTIVE
→ AIR COMPLETE
→ MARITIME / OCEAN PHASE ACTIVE

Air completion:
- repairs current hull and shield;
- advances the campaign-owned phase authority from AIR to OCEAN exactly once;
- switches the current combat mode through the existing `_apply_combat_mode()` path;
- starts the Ocean combat outcome attempt;
- displays `AIR SECURED // MARITIME PHASE ACTIVE`.

Developer F4/TAB testing remains temporary and cannot rewrite campaign progression. Leaving developer mode restores the campaign-owned phase.

## Reference basis
The transition framing uses primary military doctrine as a structural reference, not as a claim that Vector Wars is a realistic simulator.

- Air Force Doctrine Publication 3-04, Countersea Operations, describes airpower supporting maritime operations through protection, reach, ISR, and strike capability in the maritime domain.
  https://www.doctrine.af.mil/Portals/61/documents/AFDP_3-04/3-04-AFDP-Countersea-Ops.pdf
- U.S. Navy doctrine describes sea control as control of designated sea areas and associated airspace/underwater volume, achieved by neutralizing hostile aircraft, ships, and submarines, and treats sea control as a requirement for many naval operations.
  https://www.history.navy.mil/research/library/online-reading-room/title-list-alphabetically/s/strategic-concepts-usnavy.html
- Air Force Doctrine Publication 3-01 emphasizes counterair as part of a larger coherent plan tying objectives, effects, and tasks to an operational end state.
  https://www.doctrine.af.mil/Portals/61/documents/AFDP_3-01/3-01-AFDP-COUNTERAIR.pdf

Vector Wars simplifies this into a readable campaign sequence: secure the ground operation, establish air control, then move into maritime combat. Exact enemy counts, transition timing, and encounter composition remain gameplay design choices.

## Visual/UI scope
No new panel was added. The transition notice reuses the existing centered notice region. `AIR SECURED // MARITIME PHASE ACTIVE` is 36 characters, shorter than the existing 45-character Ocean objective `SINK HOSTILE WARSHIPS AND SURVIVE AIR ATTACKS`.

## Frozen
Ground operation/redeploy, Air objective counts, Ocean combat implementation, weapons, renderer, audio system, music work, F4 developer gate, and HoloVerse hooks are otherwise unchanged.
