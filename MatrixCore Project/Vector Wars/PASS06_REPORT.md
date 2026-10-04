# Vector Wars Pass 06 — Ground → Air Progression

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce unavailable in container)

## Single task
Connect the completed Ground operation to the Air combat phase in normal progression without changing Air gameplay itself.

## Changes
- Added `phase_progression.py` as campaign-owned phase authority.
- Normal campaign starts in GROUND.
- Completing the accepted Ground operation advances exactly once to AIR.
- Existing combat-mode switching code performs the physical Ground → Air transition.
- Air outcome state is explicitly started after transition.
- Leaving F4 developer mode restores the campaign-owned phase, so TAB testing cannot bypass progression.
- F3 diagnostics now show the campaign-owned phase.

## Frozen
- Ground objectives and redeploy behavior.
- Air combat design.
- Ocean combat design.
- Weapons, enemies, vehicle behavior, audio assets, renderer, and HoloVerse hooks.

## Visual boundary
No new normal-play panel was added. The completion notice uses the existing centered audio-notice region. F3 gained one diagnostic line only. Native Pygame screenshots could not be produced in this container because pygame-ce is unavailable.
