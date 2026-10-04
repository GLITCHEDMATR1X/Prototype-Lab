# Vector Arena — Strategic Arena Architecture Pass 07

Vector Arena remains a standalone Panda3D first-person arcade shooter and an optional same-window HoloVerse native dimension. Pass 07 preserves Pass 06 scale/palettes and the complete horde/evolution/Guardian/audio stack, while giving each arena family its own strategic solid architecture.

## Arena architecture families

1. **Prism Foundry — Foundry Pillars**: paired tall pillars, machinery banks, and a displaced reactor create cross-lanes and readable pockets while keeping spawn center clear.
2. **Neon Canyon — Canyon Walls**: long wall runs form broad combat canyons with deliberate breaks for flanking.
3. **Frost Circuit — Crystal Barriers**: thin elongated blockers and an offset frost spire cut long sightlines without sealing routes.
4. **Data Storm — Broken Data Walls**: segmented walls are separate physical pieces, so every visible gap is genuinely traversable.
5. **Redline Colossus — Colossus Monoliths**: large monoliths and outer bastions create the heaviest battlefield while preserving central circulation.

## No-hidden-blocker authority

Pass 07 uses one source of truth for strategic solid architecture:

```text
architecture_pieces_for_profile()
        ↓
visible opaque solid
        +
matching gameplay blocker
        +
weapon / repulsor occlusion
```

There is no second generic cover-layout table. Decorative seams sit on the authoritative solids and do not create extra collision.

Spawn gates are intentionally **phase-safe** and now look like open hardlight wireframes rather than solid opaque pylons. The playable outer limit is also shown by a **radial hardlight boundary on the exact movement radius**, eliminating the old square-wall/circular-clamp mismatch.

Every family/set is automatically checked for:

- solid-vs-solid overlap;
- player reconstruction-center clearance;
- spawn-gate clearance;
- outer-boundary clearance;
- breach-core placement clearance;
- hazard placement clearance;
- center → every spawn gate reachability;
- center → every breach point reachability;
- center → every hazard point reachability;
- solid cover blocking hitscan;
- open space not being falsely blocked;
- bounded obstacle counts and arena scale.

Hazard and breach seeds are retained when legal. If a family structure would occupy one, the point is moved deterministically to the nearest tested open location instead of being hidden inside cover.

## Arena size progression

```text
SET 1   radius 118   diameter 236
SET 2   radius 140   diameter 280
SET 3   radius 162   diameter 324
SET 4   radius 184   diameter 368
SET 5   radius 206   diameter 412
SET 6+  radius 228   diameter 456
```

After Set 5, arena families rotate at the bounded 228-unit radius. Enemy pool remains 32 with 22 active maximum.

## Controls

- WASD — move
- Mouse — look
- Left Mouse — pulse rifle
- Right Mouse — repulsor
- Shift — dash
- R — vent heat
- H — local help
- 1 / 2 / 3 — choose mutation after Guardian checkpoint
- TAB — return to HoloVerse when native-mounted
- ESC — local Vector Arena pause/resume in HoloVerse / exit standalone

## Existing combat systems preserved

- Seven wave types: Assault, Horde, Breach, Elite, Overload, Blackout, Guardian.
- Tactical gate charging and flank/rear roles.
- Special floor hazards with warning time and bounded damage.
- Five enemy families with staged Level 4 evolution ceiling.
- Seven encounter doctrines.
- Guardian Sentinel / Overdrive / Redline phases.
- Three between-set player mutation paths.
- 46 replaceable WAV assets with positional combat audio.
- Same-window HoloVerse native lifecycle and return telemetry.

## Validation

Run:

```bash
python -B tools/verify_pass.py
python -B main.py --game-contract-test
python -B main.py --game-result-test
python -B main.py --complete-game-test
python -B main.py --profile-test
```

The deterministic route contract and Panda3D render proof live under `verification/`.

Native Windows remains the final gameplay/audio acceptance environment because the container Python ABI does not match the supplied Panda3D Python wheel.


## Pass 07.1 — HoloVerse link hardening

Pass 07.1 does not redesign wave combat or arena geometry. It hardens the external-dimension contract used by HoloVerse:

- stable responder id `vector_arena`
- preserved portable UUID `00a52ff9-3fff-4ef3-9fc4-ebef98878ed9`
- explicit `holoverse_dimension_v1` native host contract
- same-window native adapter
- TAB remains exclusively host-owned for return
- ESC is dimension-owned local pause/resume while native-mounted
- H is dimension-owned local help while native-mounted
- Vector Arena owns and stops its local audio on exit
- no absolute HoloVerse path is stored in the game

The standalone launch path remains supported.
