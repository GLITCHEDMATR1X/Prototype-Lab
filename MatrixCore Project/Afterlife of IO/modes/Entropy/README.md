# Entropy — Pass 34: DreamCrawler Ruin Dives

**Entropy** is a timed science-fiction survival/exploration game built with pygame-ce. A complete expedition now begins on **HOME**, during the final minute before its star collapses. Recover emergency supplies, survive the first supernova, restore a disabled ship, then race through abandoned systems to recover **six Data Fragments** before their worlds disappear. The completed archive must be delivered to **Gleebs**, linking the expedition to MatrixCore.

## Campaign flow

1. **HOME — 60 seconds.** Explore the same seamless planetary system used by the rest of the game. Locate the emergency cache and put Fuel Cells and Salvage into the field pack before the star goes supernova.
2. **Emergency transfer.** The first supernova is the inciting incident rather than a normal failure. HOME is lost and the player wakes inside the ship in the next unstable system.
3. **Restore the ship.** Complete the physical station sequence: POWER → STORAGE → FUEL → NAVIGATION → COCKPIT. Storage really moves the HOME field pack into ship cargo; fuel processing uses those stored Fuel Cells.
4. **Expedition.** The cockpit starts the next system's one-minute collapse clock. Land on the system's abandoned world, locate its marked data archive, dive it with the DreamCrawler team to recover one Data Fragment, carry it back to the ship, salvage what you can, refuel, and choose when to leave.
5. **Archive 6 / 6.** Recovering the sixth Data Fragment changes the objective to the cockpit data link.
6. **Gleebs.** Transmit the completed archive to Gleebs. The run ends on the MatrixCore-linked expedition-complete screen.

Pass 32 preserves Pass 31's player-owned departure gate: new-system hyperdrive is locked while the current Data Fragment goal is unresolved. It unlocks only after the goal is **SECURED** or becomes **MISSED** because the target world is permanently lost. A missed required fragment is reassigned in the next system, so the six-fragment campaign cannot dead-end.

All twelve established world families remain in the expedition: desert, ice, jungle, volcanic, crystal, oceanic, fungal, rust, salt, abyss, storm, and roseglass. Seamless surface streaming, salvage/fuel processing, solar erosion, ship upgrades, supernova pressure, black-hole deterioration, and persistent saves remain part of the game.



## Pass 34 — DreamCrawler ruin dives (Afterlife of IO mode hub)

Entropy is the endgame mode of **Afterlife of IO** (title → MODES → ENTROPY, unlocked by finishing the Afterlife campaign). Hosted there it adopts Afterlife's window, and its exit option reads **RETURN TO AFTERLIFE**.

The marked data archive is now a real place:

1. Walk to the marked archive ruin and press `E` — the nine-bot DreamCrawler team dives in, in the same window.
2. Floor 1: find the stairs down. Floor 2: the vault. A WARDEN crawler guards the Data Fragment; any explorer can take it.
3. Regroup at the **ASCENT LINE** to climb out. You surface **carrying** the fragment: return to the ship (`Tab`) and secure it at **CARGO / DATA ARCHIVE**. Lift-off and warp stay locked until it is secured.
4. Underground the collapse clock runs at **1/4 speed** and freezes while the dive is paused (`Esc`). A retreat or a downed diver leaves the fragment below — press `E` to dive again while the system survives. A missed archive is still reassigned by the campaign.

If `modes/DreamCrawler` is missing, Entropy falls back to the Pass 33 instant surface recovery. Verify with `python tools/verify_pass34_ruin_dive.py`.

## Pass 33.2 HOME-start authority

Entropy stores campaign saves in the per-user application-data folder rather than inside the shipping ZIP. A newer local save could therefore survive package replacement and resume an impossible zero-progress expedition in space. Pass 31 attempted to migrate that state, but its gate required an old campaign-intro revision. If a newer build had already stamped revision 1 onto the bad save, the migration was skipped.

Pass 33.2 tightens the campaign invariant: `campaign_phase=expedition` + zero secured Data Fragments is valid only after the complete five-step ship boot (`POWER → STORAGE → FUEL → NAVIGATION → COCKPIT`). Any zero-fragment expedition with an incomplete boot sequence is impossible through the real campaign and is repaired to HOME. Fully booted zero-fragment expeditions and saves with recovered fragment progress remain resumable.

## Pass 33 expedition identity

Pass 33 makes successive abandoned-system runs easier to distinguish without adding another resource, weapon, hazard, or save field. It builds identity from systems Entropy already owns.

- **Twelve archive profiles:** every world class now exposes a compact world-record identity such as DUST RECORD, CRYO RECORD, SPORE RECORD, TEMPEST RECORD, or FRACTURE RECORD.
- **Six archive slots:** the six required Data Fragments read as Archive 1/6 through Archive 6/6 and softly prefer different existing ruin families (Survey, Observation, Defense, Signal, Remnant, Continuity) while preserving the same reachable target-distance pool.
- **Varied consecutive systems:** new systems reroll their seed before commitment when necessary so the next abandoned world strongly prefers a different hazard family and world class from the system just left. Existing saved systems are never regenerated.
- **Readable arrival:** warp arrival announces archive slot, world identity, record identity, and hazard family. Surface HUD and ship storage use the same terminology.
- **Dead-world continuity:** if the target dies while its fragment is already being carried, the archive record identity survives target retirement and remains correct when the player stores it aboard ship.

No terrain geometry, landmark placement, hazard values, 60-second collapse timing, resource balance, upgrade values, controller mapping, music routing, or save schema changed.

## Pass 32 smoothness and expedition feedback

Pass 32 is a behavior-preserving performance/feel pass. It does **not** lower terrain quality, remove world families, change the 60-second collapse balance, alter controller mapping, or change save schema v5.

- **4K presentation:** the authored 1920×1080 frame now uses exact integer scaling for exact multiples such as 3840×2160 instead of filtered resampling every frame. Fractional and downscaled windows still use `smoothscale`.
- **Frame pacing:** raw wall time still owns lifecycle and collapse deadlines, while motion/animation delta is capped at 50 ms so a short OS or asset hitch cannot throw the ship/camera across the scene.
- **Starfield:** the hot quaternion projection path is inlined and fast-motion LOD no longer creates a sliced star list each frame. Star count and authored distribution are unchanged.
- **CRT pass:** radiation/film noise still changes at its authored 25 Hz rate, but duplicate 60 Hz rebuilds are skipped. Static scanlines and vignette are precomposed after resize, reducing the frame loop from two static full-screen FX blits to one.
- **UI/interior:** reusable panel fills, rendered text, collapse-edge masks, cockpit glow labels, HUD notices, and interior font objects are cached instead of being recreated continuously.
- **Outcome clarity:** planetfall explicitly reports an active data goal and locked warp; storing data reports archive progress and when hyperdrive becomes available; lost-world behavior remains the Pass 31 SECURED/MISSED/CARRYING state machine.

## Surface hazard personality

Pass 26 turns the four existing hazard labels into lightweight gameplay rules without adding a new health/currency system:

- **HEAT** — thermal load rises as you travel away from the landed ship; high load modestly slows traversal. Returning toward the ship cools the rig.
- **COLD** — cryogenic drag increases with distance from the ship and produces the strongest sustained mobility penalty.
- **BIOLOGICAL** — deterministic spore blooms cycle on and off; an active bloom temporarily slows surface travel.
- **ANOMALOUS** — long-range Data Fragment guidance drifts in both direction and displayed range. Closing on the archive resolves the signal cleanly.

The existing **Surface Rig** upgrade now also mitigates hazard severity (12% / 24% / 38% at levels 1–3), so an existing progression choice becomes more useful without creating another equipment track. Surface hazards remain non-lethal; stellar collapse and black-hole pressure remain Entropy's hard failure condition.

## Surface landmark identity

Pass 27 gives every established terrain family a deterministic large-scale visual anchor so surfaces read as memorable places instead of only procedural fields. Each planet receives three visual-only landmarks, placed clear of the landed ship and authored archive ruins. They have no collision, resource reward, or mission-state authority.

- **Desert:** Sun Ring
- **Ice:** Cryo Needles
- **Jungle:** Root Cathedral
- **Volcanic:** Caldera Crown
- **Crystal:** Prism Choir
- **Oceanic:** Flood Pylons
- **Fungal:** Spore Crown
- **Rust:** Foundry Ribs
- **Salt:** Mirror Obelisk
- **Abyss:** Void Lantern
- **Storm:** Storm Mast
- **Roseglass:** Roseglass Fan

The primary landmark identifies itself only when the player is nearby; no new permanent HUD panel was added. Objective arrows, hazard information, Data Fragment routing, and the 60-second collapse pressure remain the gameplay authority.

## State-aware score

Pass 28 replaces the old sequential music playlist with one campaign-aware streamed score state. The user-supplied `MCF24.mp3` remains untouched and is the long-form expedition theme. Four deterministic seamless WAV loops support the story states around it:

- **HOME SIGNAL** — HOME before the final critical-collapse window.
- **SHIP RECOVERY** — the disabled-ship POWER → STORAGE → FUEL → NAVIGATION → COCKPIT sequence.
- **EXPEDITION / MCF24** — normal orbit, surface, ruin and operational-ship exploration.
- **COLLAPSE PRESSURE** — CRITICAL, SUPERNOVA and BLACK HOLE states.
- **GLEEBS LINK** — six-fragment delivery and the MatrixCore-linked completion screen.

The score follows campaign/collapse state rather than camera mode, so entering the ship or landing during an ordinary expedition does not restart the music. Every state loops until the state changes. The previous stream is stopped before a new one loads, and failure screens deliberately silence the score. Master, Music, Ship + Effects and World Ambience remain independent saved volume categories.

## Controller-first input

Pass 29 adds a mapped game-controller layer across the full expedition without replacing the established keyboard/mouse controls. The active controller uses SDL's standardized controller mapping rather than raw button numbers, so common mapped pads share one stable action layout. Menus use direct focus navigation instead of an analog mouse cursor.

- **Menu / Pause:** D-pad or left stick selects, `A` confirms, `B` backs/resumes, `View` opens controls/mission context, `Menu` pauses.
- **Flight:** left stick thrust/strafe, right stick yaw/pitch, `LT/RT` vertical thrust, `LB/RB` roll, `A` boost, `B` brake, `X` ship interior, `Y` view, D-pad Right warp, D-pad Left dampers.
- **Surface:** left stick/D-pad move, `A` recover/process, `X` ship interior, `B` return to orbit, `Y/View` mission brief.
- **Ship interior:** left stick/D-pad move/select, `A` use/install, `B` back/close, `X` take off, `Y/View` mission brief.

Controller disconnect and window focus loss pause the timed expedition before collapse time advances. Keyboard/mouse remain available as a fallback. Data Fragment recovery also no longer contains any dormant objective-auto-warp path: after recovering data, the player still chooses how much salvage risk to take and when to depart.

## Controls

### Flight

- `W / S`: forward and reverse thrust
- `A / D`: strafe
- `Space / Ctrl`: vertical thrust
- `Q / E`: roll
- Mouse: yaw and pitch
- `Shift`: boost
- `X`: brake
- `C`: inertial dampers
- `V`: cockpit / third-person view
- `F`: warp after the current system goal is secured or missed
- `Tab`: ship interior
- `M`: mission brief
- Backtick (`` ` ``): pause or resume
- `F11`: fullscreen toggle

### Planet surface

- `WASD`: move
- `E`: recover/process nearby object or Data Fragment
- `Tab`: enter ship while nearby (locked during HOME emergency)
- `Space`: return to orbit (locked during HOME emergency)
- `M`: mission brief
- Backtick (`` ` ``): pause or resume

### Ship interior

- `WASD`: move
- `E`: use station
- `Tab`: return to previous view (locked during initial ship recovery)
- `Space`: take off after the ship is operational
- Backtick (`` ` ``): pause or resume

## Runtime

Entropy uses **pygame-ce**, not Panda3D. The source build requires Python 3.10+ and:

```text
pygame-ce>=2.5.7,<2.6
```

Run with:

```bash
python main.py
```

Optional safe launch without audio:

```bash
python main.py --no-audio
```

## Save and configuration locations

Writable player data remains outside the shipping folder. On Windows the normal location is:

```text
%LOCALAPPDATA%\GLITCHED MATRIX\Entropy
```

Untouched/new saves begin on HOME. Pass 31 also detects pre-campaign **zero-progress** saves that were previously migrated straight into space and routes those runs through HOME once. Real campaign saves with ship-boot progress and/or recovered Data Fragments resume normally. The save schema remains **version 5**.

Pass 30 hardens that same save format rather than replacing it:

- `saves/save_state.json` is the active atomic save.
- `saves/save_state.previous_good.json` keeps the last validated generation.
- If the active JSON is truncated/corrupt, Entropy automatically restores the previous-good generation and tells the player.
- Active runs checkpoint every 20 seconds and when a pause/lifecycle interruption begins.
- Focus loss, controller loss, and a long process-resume frame pause the expedition before the 60-second collapse clock can consume the interruption.
- `crashes/Entropy_crash_*.zip` contains local-only crash diagnostics. Nothing is uploaded automatically and save-file contents are never bundled.

## Pass 31 expedition flow integrity

- Fresh/untouched runs begin directly on the HOME surface; legacy zero-progress saves that skipped the prologue are repaired into HOME once.
- Planetfall is a committed two-stage handoff. The atmosphere transition remains the only visible scene while the surface is prepared, and the next rendered frame is the loaded surface—never an orbital flash.
- Known planet/system loading stalls are excluded from the Pass 30 long-frame suspend detector, preventing false double-pauses during planet entry.
- A dead/unlandable objective world immediately loses its Data Fragment waypoint.
- If required data was never recovered before that world died, the goal becomes MISSED, warp unlocks, the archive count does not advance, and that required fragment is returned to the next-system target cycle.
- If the fragment is already being carried when the world dies, the waypoint is retired but hyperdrive remains locked until the data is secured aboard the ship.
- New-system warp is unavailable while a live system goal remains unresolved. Controller D-pad Right and keyboard `F` share the same gate.

## Status

Pass 32 preserves the Complete Expedition campaign, hazard personality, landmark identity, state-aware score, controller-first input, save/crash resilience, economy, upgrades, collapse rules, and save schema v5 while retaining the Pass 31 flow fixes and reducing avoidable per-frame work, 4K scaling cost, and hitch-driven motion jumps.
