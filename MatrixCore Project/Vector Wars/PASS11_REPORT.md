# Vector Wars Pass 11 — Ocean Sea-Control Operation Loop

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING
TARGET-RUNTIME TEST: NOT RUN (pygame-ce unavailable in container)

## Single task
Give the existing Ocean front a finite mission loop without changing Ground/Air progression, adding new weapons, or adding new UI panels.

## Operation
1. BREAK SURFACE ACTION GROUP — destroy 4 hostile warships.
2. DEFEAT MARITIME AIR ATTACK — destroy 2 hostile helicopters.
3. SEA CONTROL ESTABLISHED — Ocean outcome becomes COMPLETE and current hull/shields are restored.

Kills are banked even when performed out of stage order. Exact target counts are gameplay tuning, not real-world force ratios.

## Reference basis
- U.S. Navy sea-control doctrine: control of specified maritime areas includes the associated airspace and underwater volume and is achieved by neutralizing hostile aircraft, surface ships, and submarines.
- OPNAVINST 3501.316C: a Surface Action Group is a flexible tactical element contributing to sea control and related naval missions.
- U.S. Navy MH-60R fact file / HSM mission material: MH-60R helicopters perform surface warfare and anti-submarine warfare and operate from surface combatants.

These sources inform terminology and mission structure. Vector Wars remains an arcade combat game, not a military simulator.

## Regression / integrity
- Pass 10 regression authority ran before editing: 11/11 PASS.
- Expanded Pass 11 regression authority after editing: 13/13 PASS.
- Warship player kills are typed WARSHIP on bullet and missile paths.
- Helicopter player kills are typed HELICOPTER on bullet and missile paths.
- No generic Ocean kill-attribution hook remains.
- F4/TAB developer gating and Ground/Air progression are unchanged.

## Visual boundary
No new panel was added. Ocean objective text reuses the same top-center objective region and Ocean diagnostics reuse the existing F3 diagnostic line.
Fresh rendered visual acceptance remains pending because pygame-ce 2.5.7 cannot execute in this container.
