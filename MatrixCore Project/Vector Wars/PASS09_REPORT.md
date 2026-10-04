# Vector Wars Pass 09 — Air Superiority Operation Loop

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce unavailable in container)

## Regression gate
Pass 08 authority ran first and passed 8/8. No pre-existing regression blocked this task.

## Single task
Turn AIR from an open-ended combat sandbox into a finite operation loop using the existing fighter and UFO combat systems.

## Air operation
1. **Establish Air Control** — destroy 6 hostile fighter craft.
2. **Intercept UFO Contacts** — destroy 2 UFOs.
3. **Air Secured** — Air outcome becomes COMPLETE and the current player craft receives full hull/shield repair-resupply.

Kills are banked even if performed out of order, so an early UFO destruction is not discarded. Completion does not yet transition to Ocean; that remains a later single-task pass.

## Real-data reference boundary
The structure is informed by U.S. Air Force doctrine defining air superiority as control of the air sufficient to permit operations without prohibitive interference, and by the National Museum of the U.S. Air Force description of establishing air superiority before later battlefield phases. The exact 6-fighter / 2-UFO counts are deliberate gameplay tuning, not claims about real military force ratios.

Sources:
- Air Force Doctrine Publication 3-01, Counterair Operations: https://www.doctrine.af.mil/Portals/61/documents/AFDP_3-01/3-01-AFDP-COUNTERAIR.pdf
- National Museum of the U.S. Air Force, The Pillars of Tactical Airpower: https://www.nationalmuseum.af.mil/Visit/Museum-Exhibits/Fact-Sheets/Display/Article/4273897/the-pillars-of-tactical-airpower/

## Visual/UI scope
The existing top-center objective line now shows Air-operation progress instead of the generic `CLEAR HOSTILE SHIPS AND UFO VECTORS` text. No new normal-play panel was added. F3 diagnostics gain one Air-operation line in the already-used diagnostics stack.

## Frozen
Ground gameplay/redeploy/progression, Ocean gameplay, F4 developer gating, weapons, renderer, audio system, and HoloVerse hooks are otherwise unchanged.
