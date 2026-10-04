# Vector Wars Pass 18 — Secondary Weapon Authority Repair

Status: CANDIDATE — native pygame-ce runtime acceptance pending.

## Regression-first gate
Pass 17 fresh extraction passed 23/23 before this pass began.

## Regression found
Ocean RMB was owned by two weapon paths in the same frame:
1. the generic Ship.update() homing-missile path, and
2. the Ocean-specific torpedo path.

This meant Ocean secondary fire could attempt both a normal missile and a torpedo from one RMB input.

## Repair
Added `weapon_pacing.py` as the single player-secondary cadence authority.

- AIR: generic homing missile, 1.25 s recycle
- GROUND: generic homing missile, 1.60 s recycle
- OCEAN: torpedo only, 2.40 s recycle

The HUD cooldown now reads the same phase-specific timing authority used by firing. AI craft retain their pre-existing `self.missile_cd` behavior.

## Reference framing
- U.S. Air Force / National Museum: M61A1 Vulcan is capable of 6,000 rounds per minute. This supports keeping primary gunfire as the rapid continuous weapon layer.
- U.S. Navy budget/readiness material: MK 54 is a lightweight torpedo used against submarines from surface and airborne platforms. Vector Wars deliberately uses its Ocean torpedo as an arcade anti-surface weapon; that target role is a documented gameplay deviation, not a realism claim.

No real-world reload/cycle value was copied into the game. The 1.25 / 1.60 / 2.40 second values are gameplay tuning chosen to preserve phase identity.

## Regression result
Expanded authority: 25/25 PASS.

No HUD layout, campaign objective, save, music, enemy population, or movement-speed authority changed.
