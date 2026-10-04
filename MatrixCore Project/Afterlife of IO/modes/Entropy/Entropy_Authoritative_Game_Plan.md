# Entropy — Authoritative Game Plan

**Current baseline:** Pass 29 — Controller-First Expedition  
**Engine:** pygame-ce  
**Campaign:** HOME → ship recovery → six Data Fragments → Gleebs / MatrixCore

## Direction lock

Entropy is a compact timed survival-exploration game, not a general space sandbox. Every major feature must support the pressure of preserving useful material and lost information before a solar system collapses.

The game begins on **HOME**, which is deliberately not a special gameplay biome. It is generated from the same planetary/world rules as the rest of Entropy and is already under the standard one-minute collapse clock. The emotional difference comes from context: it is the player's home, and it is about to be lost.

The required campaign archive is **six Data Fragments**. Each post-HOME system presents one abandoned objective world with one recoverable fragment. Recovering it does not auto-warp the player. The player decides how long to continue salvaging, when to return to the ship, when to refuel/upgrade, and when to leave.

## Complete expedition

1. **HOME / final minute**
   - Start on foot on HOME instead of in space.
   - Display the normal 60-second stellar-collapse clock immediately.
   - Provide a readable emergency cache containing Fuel Cells and Salvage.
   - Recovered HOME material goes into a small field pack, not magically into distant ship cargo.
   - HOME forbids normal takeoff/ship escape. The first supernova is guaranteed narrative evacuation.

2. **Emergency transfer / disabled ship**
   - HOME supernovas at timer zero.
   - Transition to the next generated unstable system.
   - Player wakes inside the ship interior with the external collapse clock frozen until the ship is operational.
   - Preserve the HOME field pack through the transfer.

3. **Physical ship onboarding**
   - The ship itself is the tutorial; avoid a large modal tutorial.
   - Required sequence: **POWER → STORAGE → FUEL → NAVIGATION → COCKPIT**.
   - POWER restores ship operation.
   - STORAGE transfers the field pack into persistent ship cargo.
   - FUEL processes stored Fuel Cells using the existing fuel system.
   - NAVIGATION initializes expedition routing.
   - COCKPIT starts the first abandoned-system collapse clock and launches the expedition.
   - Out-of-order station use should be refused with short contextual feedback.

4. **Abandoned-system loop**
   - One visible landable world per generated system remains the clear objective.
   - The world uses one of the existing twelve terrain families.
   - The system begins with a 60-second survival clock once the cockpit releases the player into the expedition.
   - Land, follow the Data Fragment signal, recover the marked archive, and optionally process surface material.
   - Return to the ship to store/refuel/repair/upgrade.
   - Warp manually when ready. Data Fragment recovery never forces an automatic transition.
   - If the star reaches supernova, preserve the existing collapse/shock/ejection rules; continued deterioration may become a black hole.

5. **Six-fragment objective**
   - Archive progress is always legible as `DATA X/6` where appropriate.
   - Each system can increase the campaign count at most once.
   - Duplicate recovery must be rejected.
   - Data Fragments are campaign information, not Fabricator currency.
   - Existing historical `relic_cores` in old saves may remain usable as legacy upgrade tokens but must not be confused with Data Fragments in the current campaign UI.

6. **Gleebs / MatrixCore ending**
   - Fragment six changes the objective from exploration to delivery.
   - The cockpit becomes the final data-link station.
   - Player transmits the complete abandoned-world archive to **Gleebs**.
   - End on a dedicated non-overlapping completion screen naming Gleebs and confirming the MatrixCore link.
   - Do not require a combat boss; Entropy's climax is successfully preserving the information.

## Systems to preserve

- Fixed 1920×1080 virtual presentation with fit scaling.
- One-minute stellar-collapse pressure.
- Supernova and black-hole lifecycle.
- Full 6DOF flight.
- Cockpit / third-person views.
- Seamless deterministic top-down planetary streaming.
- Twelve existing world families and weather identities.
- Salvage and Fuel Cell economy.
- Four existing ship upgrade tracks.
- Ship interior as persistent between-system connective tissue.
- Save/settings/log files outside the shipping directory.
- Sun reset/safety behavior and bounded solar-erosion visuals.

## Hazard personality — Pass 26

- **HEAT:** thermal load rises with distance from the landed ship and modestly reduces traversal speed at high load. Ship proximity is the refuge.
- **COLD:** cryogenic drag scales with distance and produces a stronger sustained mobility penalty.
- **BIOLOGICAL:** deterministic periodic spore blooms temporarily slow travel, creating learnable timing windows rather than random punishment.
- **ANOMALOUS:** distant Data Fragment guidance drifts in direction/range; close-range navigation resolves cleanly.
- **Surface Rig:** existing levels now mitigate all hazard severity by 12% / 24% / 38%.
- Surface hazards are intentionally non-lethal. The stellar collapse remains the run's primary hard failure pressure.


## Surface landmark identity — Pass 27

- Every established terrain family receives a distinct authored landmark silhouette.
- Each generated surface receives three deterministic visual anchors.
- Landmarks stay clear of the landed ship and archive ruins and do not participate in collision.
- Landmarks are not harvestable, do not grant rewards, and do not become mission objectives.
- The primary landmark identifies itself only at nearby range, preserving HUD discipline.
- Purpose: make a 60-second expedition route more memorable and navigable without adding another gameplay system.

## State-aware score — Pass 28

- HOME, ship recovery, normal expedition, critical collapse, and Gleebs delivery now have explicit score states.
- Original `MCF24.mp3` remains untouched as the long-form expedition theme.
- Four deterministic support loops frame HOME, disabled-ship recovery, collapse pressure, and the Gleebs handoff.
- Music state follows campaign/collapse authority instead of SPACE/SURFACE/INTERIOR view changes.
- Active tracks loop indefinitely until the authoritative state changes; state changes stop the prior stream before loading the next.
- Failure deliberately silences music. Pause/settings preserve the current score.
- Master, Music, Ship + Effects, and World Ambience remain independent saved categories.

## Pass 28 handoff status

Controller-first navigation/gameplay and pause/settings accessibility was the Pass 28 handoff priority and is completed by Pass 29. Save/crash hardening and later platform preparation remain ahead. Entropy should not expand into a feature-heavy sandbox before those fundamentals are complete.


## Pass 29 controller-first contract

- Preserve keyboard/mouse controls while adding one mapped primary-controller path across every playable state.
- Use direct UI focus navigation rather than a controller-driven mouse cursor.
- Controller disconnect and focus loss pause the timed collapse loop before simulation time is consumed.
- Keep the controller provider isolated from mission logic so a future native GameInput/GDK implementation can replace the PC SDL provider without redesigning campaign systems.
- Data Fragment recovery never auto-warps. The player owns the salvage-versus-departure decision.
- Do not change save schema, resource balance, hazards, landmarks, music routing or six-fragment campaign progression in this pass.

### Next priorities after Pass 29

1. Native Windows controller acceptance with at least Xbox Wireless Controller plus reconnect/focus-loss tests.
2. Save/crash hardening around campaign checkpoints and suspend/resume.
3. Achievement/platform preparation after the complete controller build is stable.
4. Native GDK/GameInput/user-binding work only when moving from PC prototype readiness into an approved Xbox development environment.

## Pass 30 save/crash + suspend/resume contract

- Preserve save schema v5; harden storage around the existing payload instead of forcing a migration.
- Publish saves atomically through a same-directory temporary file, flush + fsync before replacement, and keep one validated `save_state.previous_good.json` generation.
- If the active save cannot be parsed, automatically recover the previous-good generation and repair the primary file rather than silently starting a fresh expedition.
- Active gameplay checkpoints every 20 seconds and on pause/lifecycle interruption. Normal transition checkpoints remain intact.
- A large first frame after process resume is treated as a lifecycle interruption and pauses the expedition before collapse/physics timing can consume the gap.
- Controller disconnect and window focus loss remain pause-safe and now also trigger a persistence checkpoint.
- Track active/clean/crashed session state outside the shipping folder so the next launch can identify an unexpected prior termination.
- Crash diagnostics are local-only, non-zero, integrity-checked ZIP bundles containing traceback, bounded runtime/fault log tails, build/runtime metadata and minimal gameplay context. Do not include save contents, environment dumps, usernames, or automatic upload.
- Keep Complete Expedition, six-fragment progression, hazards, landmarks, music, controller mapping, resource balance, upgrades and collapse damage rules frozen.

### Next priorities after Pass 30

1. Native Windows acceptance: Xbox Wireless Controller connect/reconnect, focus loss, long suspend/resume, save recovery and crash-bundle smoke test.
2. Achievement/platform foundation only after that native acceptance is clean.
3. GDK Game Saves/GameInput/user binding when preparing an approved Xbox development build.


## Pass 31 expedition-flow contract

- Fresh runs begin on the **HOME surface**, not in orbit. A pre-campaign zero-progress save that previously skipped HOME is routed through the prologue once; real campaign progress is preserved.
- Planet entry is a **committed transition**: atmosphere-entry visuals remain authoritative until terrain/surface setup is complete, then the next visible frame is the surface. Never reveal orbital space between those states.
- Deliberate planet/system loading stalls are not suspend/resume events and must not trigger the lifecycle auto-pause.
- New-system hyperdrive is locked while the current Data Fragment goal is active. It unlocks only when the goal is **SECURED** or **MISSED**.
- When collapse/destruction makes the target world inaccessible, retire its waypoint immediately. If the Data Fragment was not secured or carried, mark the goal MISSED without increasing the archive count.
- A MISSED required fragment returns to the target pool in the next system. The campaign must never dead-end because a required item died with a planet.
- If data was already carried off-world, preserve it, retire the dead-world waypoint, and keep hyperdrive locked until ship storage secures the fragment.
- Preserve six-fragment/Gleebs progression, hazards, landmarks, state-aware music, controller mapping, save schema v5, crash recovery, economy, upgrades, and collapse damage rules.


## Pass 33 expedition-identity contract

- Keep Pass 31 flow integrity and Pass 32 smoothness authoritative.
- Every one of the twelve established surface classes has a compact Data Archive record identity derived from the existing world family; no new lore-dependent collectible system is introduced.
- The six required archive slots softly prefer six different existing ruin families while preserving the established reachable target pool and route-distance balance.
- When committing a brand-new system, prefer a world whose hazard family differs from the system just left; at minimum avoid an immediate repeat of the same world class when a different candidate is available. Existing saved systems are never rerolled.
- A carried fragment preserves its originating archive identity after target-world retirement.
- Keep save schema v5, six-fragment progression, collapse timing, hazard values, landmarks, resources, upgrades, controller mapping, music routing and crash/suspend resilience unchanged.
