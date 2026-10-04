# HEX CONTRACT — Pass 32: Finalization UX / Audio / Windows Build Fixes

Pass 31 replaces the old optional music drop-in folder with the final normalized soundtrack supplied for HEX CONTRACT. The game keeps one streamed music context active at a time: MCF28 loops throughout all out-of-battle/menu/meta states; MCF12, MCF18, and MCF22 loop in Purge, Recovery, and Rescue respectively; MCF26 takes over once a Sovereign enters and remains the battle score until the mission sequence is left.

All five source fragments were converted to 48 kHz stereo OGG and normalized to approximately -20 LUFS. Excess leading/trailing near-silence was trimmed where present so loops do not pause for several seconds between repeats. Music gain is capped to 95% of the configured SFX gain, preserving combat and interface readability even if the Music Volume slider is raised. Music context changes stop the prior streamed track before loading the next one, so menu, battle, and Sovereign music do not overlap.

Routing and normalization metadata live in `assets/music/music_manifest.json` and `assets/music/normalization_report.json`.

# HEX CONTRACT — Pass 30: Finalization Prep + Adaptive Borderless Desktop

Pass 30 freezes gameplay after the Pass 29 renderer repair and prepares the full title for finalization. Normal launch now uses the active desktop's current resolution in borderless desktop fullscreen while the game continues rendering on its fixed 1920×1080 canvas. The monitor is not asked to switch to a different physical resolution. Non-16:9 desktops are letterboxed/pillarboxed instead of stretched, Windows enables per-monitor-v2 DPI awareness before SDL video initialization, and F11 switches between borderless desktop and a safe 1280×720 window.

`--windowed` forces the safe window for diagnostics and captures. `--display-index N` selects an SDL desktop when multiple displays are exposed. The packaged Windows build must pass `--display-self-test` before it can report PASS. See `FINALIZATION_READINESS.md`.

# HEX CONTRACT — Pass 29: Full Code Audit + Mission Renderer Fix

Pass 29 performs a full source audit after the Windows mission-launch crash and finds a concrete renderer regression that earlier compile-only checks could not detect. `Renderer._draw_contract_site()` called `self._draw_world_obstacle(...)`, but the method had disappeared after two Pass 21 hierarchy methods were accidentally merged. The surviving `_draw_obstacle_foundation()` also contained an unintended direct recursive call. Both conditions are fatal once a mission battlefield begins rendering.

The fix restores the Pass 21 separation between `_draw_obstacle_foundation()` and `_draw_world_obstacle()` while preserving the later Pass 22+ ringless spawner treatment, Pass 21 visual hierarchy, all nine layouts, sidekick squads, achievements, controller support, crash reporting, and Microsoft full-title preparation.

Pass 29 adds `tools/pass29_code_audit.py`, which checks Python 3.12 parsing/compilation, duplicate definitions, mutable defaults, unresolved relative imports, undefined `self.method()` calls in shipping runtime classes, unexpected direct recursion, JSON parsing, Renderer/Mission API contracts, App component APIs/states, a 36-case mission first-update matrix, and all nine contract-site render paths. When pygame-ce is unavailable, the last two checks use an embedded geometry/drawing compatibility stub and are explicitly not treated as native runtime proof.

# HEX CONTRACT — Pass 28: Mission Stability Hotfix

Pass 28 hardens the real mission transition after a user-reported Windows crash. Freshly constructed missions must now pass a launch-state preflight before sidekick costs/profile state are committed. The live mission renderer now draws joined sidekicks. Crash diagnostics are durable: session breadcrumbs and emergency records are fsynced, crash bundles are integrity-tested before promotion, and the faulthandler file is never a misleading 0 KB placeholder.

# HEX CONTRACT — Pass 27: Mission Crash Capture & Recovery

HEX CONTRACT is a source-only Pygame cyber-fantasy guild simulator for the GLITCHED MATRIX Prototype Lab. The player selects a contract, deploys an autonomous lead hero, issues a non-binding guild order, equips a preparation kit, optionally spends banked Sidekick Perks to recruit up to two additional heroes, and observes a personality-driven mission whose consequences persist across the guild roster.

Pass 16 masters the presentation around the accepted Pass 14 tactical worlds and Pass 15 actor identities. Combat statistics, hero doctrines, contracts, bonds, economy, death/restoration, equipment, HEX Links, collision radii, pathfinding, LOS, destructible cover, and world layouts are preserved. Pass 31 now ships the finalized normalized Sound Fragment score alongside the existing atmosphere, combat feedback, contract ambience, and action/impact cues.

The current Prototype Lab deliverable remains source-only. Microsoft preparation treats HEX CONTRACT as a full title; native Windows/GDK packaging is a later platform gate rather than a demo path.




## Pass 27 mission crash capture and recovery

Pass 27 responds to a real mission-launch crash without guessing at the missing Windows traceback. Mission creation is now guarded as a rollback-safe transaction and mission startup/update/frame exceptions produce a local diagnostic ZIP rather than silently terminating the game.

Windows reports are stored under `%LOCALAPPDATA%\GLITCHED MATRIX\HEX CONTRACT\crashes`. They contain sanitized traceback/runtime/mission context, not save-file contents, and nothing is uploaded automatically. See `CRASH_REPORTING.md`.

The Windows build gate now includes a packaged `--crash-reporter-test` and refuses PASS unless a synthetic mission-launch failure produces a crash ZIP. Profile schema remains v9 and the Microsoft release remains a full game.


## Pass 24 Xbox Controller + platform UX readiness

Pass 24 prepares the full HEX CONTRACT title for controller-first Microsoft platform testing without adding a hard Xbox/GDK dependency to the portable source build. Combat, balance, worlds, achievements, sidekick rules, roster persistence, and profile schema remain unchanged.

- Xbox-style controller actions are normalized into game actions rather than scattered raw button checks.
- **A** confirms/deploys/continues, **B** backs out or leaves an active contract, **X** handles recovery/mission analysis, and **Y** opens contextual settings/dossier actions.
- D-pad and left stick navigate menus. LB/RB cycle guild orders and valid sidekick combinations where appropriate.
- Title, Settings, Contract Board, Hero Select, Loadout Prep, Restore Select, Last Light, Bond Event, Pause, and Mission Result all have controller paths.
- Input prompts switch between keyboard/mouse and Xbox Controller conventions based on the last active input family.
- Active unpaused missions do not gain a persistent controller footer, preserving the gameplay safe area.
- Controller disconnect pauses an active contract when appropriate and falls back to keyboard/mouse prompts.
- Focus loss/minimize checkpoints the profile and pauses active gameplay; focus restoration never silently resumes the mission.
- `--save-root <path>` and `HEX_CONTRACT_SAVE_ROOT` can redirect profile/result files to a future synchronized platform directory while keeping legacy save behavior as the default.
- Profile schema remains **v9**. Pass 23 achievement definitions and progress remain unchanged.

### Controller staging map

```text
A       Confirm / deploy / continue
B       Back / leave active contract
X       Recover hero / mission analysis
Y       Settings / mission dossier
D-pad  Menu navigation
L-stick Menu navigation
LB/RB   Guild order / sidekick combination cycling
Menu    Field Guide or mission pause/resume
View    Reserved for future platform overlay
```

### Platform-safe save routing

```bash
python main.py --save-root "<platform save directory>"
```

or set:

```text
HEX_CONTRACT_SAVE_ROOT=<platform save directory>
```

The default remains the existing project-local profile location so Prototype Lab behavior does not regress. The abstraction exists so a future native Windows/GDK build can supply an `XGameSaveFiles`-managed/synchronized directory without rewriting the game profile system.

Pass 24 verification:

```bash
python -m py_compile main.py game/*.py tools/*.py
python tools/pass24_controller_platform_verify.py
python tools/pass22_sidekick_party_verify.py
```

Native controller/GameInput, suspend/resume, and cloud-save acceptance still require a Windows GDK environment and physical target hardware.


## Pass 22 banked sidekick squads

Pass 22 keeps every Pass 21 world/layout/material decision and adds a roster-driven squad option.

- Persistent selection/aura rings around gameplay NPCs and important objects have been removed or replaced with angular/rectangular indicators.
- A successful contract still prioritizes restoration whenever any hero is eliminated.
- If nobody is waiting to be revived, the victory banks **1 Sidekick Perk** instead.
- Sidekick Perks accumulate and remain saved until the player chooses to spend them.
- One perk recruits one active non-lead hero for the next mission.
- A mission can field **1–3 heroes total**: one lead plus up to two sidekicks.
- Recruited heroes spawn beside the lead rather than at the exact same point and maintain separated support lanes.
- Each sidekick adds **+2 initial enemies** and **+1 complication reinforcement**. Enemy/boss HP and damage are not multiplied.
- Sidekicks can fight, be targeted, and be downed; the lead hero remains mission-failure authority.
- The first sidekick remains compatible with existing HEX-link mastery/bond progression, and all deployed sidekicks build bond history.
- Profile schema is now **v8**. Old victory/restoration charges that have nobody left to restore migrate into banked Sidekick Perks.

### Sidekick flow

```text
WIN CONTRACT
→ FALLEN HERO EXISTS?
  YES: RESTORE FIRST
  NO: BANK SIDEKICK PERK
→ SAVE PERKS OR SPEND 1–2 ON A LATER MISSION
→ TEAM SIZE 1–3
→ ENEMY COUNT SCALES WITH JOINED SIDEKICKS
```

## Pass 21 world visual hierarchy

Pass 21 is a presentation-only pass over the nine approved Pass 20 maps. It does not alter world geometry, markers, AI, combat balance, layout selection, actor definitions, rewards, or collision.

- Generic grids are replaced by quieter contract-specific floor inlays, archive cells, and transit seams.
- Support cover uses lower-contrast outlines and lower texture intensity.
- Authored setpieces use stronger edges and material presence.
- Destructible shortcuts receive a distinct interactive edge treatment.
- One dominant landmark per contract leads the composition: Altar Gate, Mirror Archive, and Shrine Lane.
- Multipart setpieces receive low-value floor foundation plates; these plates are traversable and never add collision.
- Six 64×64 world textures are retuned to reinforce hierarchy rather than repeat equal visual noise.
- All nine Pass 20 layouts remain valid at the 120 px minimum obstacle gap and 36 px maximum actor radius.

Pass 21 verification commands:

```bash
python -m py_compile main.py game/*.py tools/*.py
python tools/pass22_sidekick_party_verify.py
python tools/pass21_visual_hierarchy_verify.py
python tools/pass21_visual_hierarchy_preview.py
```

## Complete game structure

- Four detailed autonomous heroes with distinct doctrines, equipment silhouettes, animation, injuries, death history, and restoration scars
- Three authored contract worlds with nine enemy identities and three signature sovereigns
- Equipment preparation, quest intelligence, guild orders, deterministic complications, and optional HEX Links
- Persistent guild treasury, renown, medbay recovery, hero strain, elimination, victory restoration, and Last Light cycles
- Six hero-pair relationships, bond events, and link mastery
- Night of Three Sovereigns linked campaign with persistent battlefield aftermaths
- Title/continue flow, contextual onboarding, settings, field guide, generated audio, profile recovery, and 720p/1080p scaling
- Prototype Lab discovery metadata and a source-only game-result packet






## Pass 19 tactical setpiece kit

Pass 19 keeps the recovered Pass 18 broken-maze footprints, marker positions, spacing contract, and gameplay source frozen while replacing repeated internal wall reads with authored cover identities. The visible setpiece pieces are the real movement, line-of-sight, and projectile-blocking rectangles used by the runtime.

- **Saint Voltage:** Flying Buttresses, Altar Gate, Choir Screens, Broken Cloister, destructible Votive Rail
- **Blackglass:** Mirror Archive, Index Engine, Stack Bridge, destructible Shard Barricade
- **Pilgrim Ossuary:** Service Hook, Signal Barricade, Shrine Lane, destructible Split Bulkhead
- 13 authored setpiece identities total
- 13 dedicated 64x64 material textures
- Pass 18 outer obstacle footprints identical
- Pass 18 marker positions identical
- 120 px minimum obstacle gap preserved
- 36 px largest actor preserved
- all required routes valid before destruction
- no extra standalone blockers added
- `main.py`, combat, AI, actors, audio, renderer, app flow, and world runtime source preserved byte-for-byte from Pass 18

Pass 19 verification commands:

```bash
python -m py_compile main.py game/*.py tools/*.py
python tools/pass14_world_verify.py
python tools/pass18_maze_verify.py
python tools/pass19_setpiece_verify.py
python tools/pass19_world_preview.py
```

## Pass 18 broken-maze tactical maps

This recovered pass starts from the user-supplied Pass 17 source package and rebuilds the missing Pass 18 world-data change only. Each contract now uses a deliberately broken-open maze grammar instead of scattered repeated blockers.

- **Saint Voltage / Broken Nave Labyrinth**
- **Blackglass / Fractured Index Maze**
- **Pilgrim Ossuary / Split Mercy Maze**
- 8 physical objects per contract
- 7 / 7 / 6 compound maze pieces
- 4 explicit access breaks per contract
- 120 px minimum obstacle gap
- all required routes valid for the 36 px largest actor before any destructible shortcut is destroyed
- Pass 17 combat/AI/audio/actor/render/app files preserved byte-for-byte
- three new 64×64 labyrinth material identities

Recovery verification commands:

```bash
python -m py_compile main.py game/*.py tools/*.py
python tools/pass14_world_verify.py
python tools/pass18_maze_verify.py
python tools/pass18_world_preview.py
```

## Pass 17 world material readability

- Physical cover now receives stronger pseudo-depth: bounded shadows, lower side faces, bright top/left rims, and darker lower edges. Collision remains exactly the same.
- Added eight specialized 64×64 material tiles for Cathedral, Blackglass, and Ossuary physical objects. Brittle cover, pillars/stacks, shrines, and structural walls now have distinct identities rather than sharing one generic family texture.
- Added a presentation-only brightness lift for the three battlefield floors/walls/grids. `MISSION_ENVIRONMENTS` and all combat data remain unchanged.
- Reinforcement gates read more clearly as recessed floor devices but remain intentionally non-colliding.
- Destroyed cover leaves richer rubble/shard detail while continuing to open a real navigation/LOS/projectile lane.
- Pass 16 music support is unchanged: add your Fragment tracks under `assets/music/`.
- GPTOOL was used as the visual fallback after Panda3D was again unavailable from the container package mirror. Individual Pass 17 world proofs score 7.00–7.13 with zero high-severity findings.

## Pass 16 presentation and audio mastering

- Added separate combat cue families for hero melee/ranged attacks, enemy melee/ranged attacks, abilities, impacts, enemy defeat, cover damage/breach, objectives, civilian links, and sovereign intro/phase/special/defeat states.
- Cue playback is rate-limited so autonomous combat remains readable instead of stacking every repeated hit into noise.
- Added four low-volume environmental beds: guild, Saint Voltage purge, Blackglass recovery, and Pilgrim Ossuary rescue.
- Added an **optional** streamed music library at `assets/music/`. WAV, OGG, and MP3 tracks are discovered automatically. The game still launches and plays normally with no music files present.
- Optional prefixes `purge_`, `recovery_`, and `rescue_` route tracks toward matching contracts; unprefixed tracks remain a general pool.
- Added a persistent **Music Volume** setting independent from SFX and ambience.
- Added deterministic contract atmosphere: embers/voltage drift in Saint Voltage, floating glass motes in Blackglass, and lateral dust/signal streaks in the Ossuary. Reduced Motion freezes this nonessential drift.
- Added richer projectile cores/trails, hit rings, subtle light pools, and sovereign arena auras without changing collision or attack ranges.
- Added a presentation-only event queue in `Mission`; after removing those cue calls, the Pass 16 simulation AST is identical to Pass 15.

### Music Fragment drop-in

Put tracks in:

```text
assets/music/
```

Examples:

```text
purge_MCF24.ogg
recovery_MCF25.ogg
rescue_MCF27.ogg
MCF28.ogg
```

The game uses `pygame.mixer.music` streaming for these long-form tracks instead of loading them into short-effect memory.

## Pass 14 tactical world foundation

- Combat playfield expanded from the old 1700×780 inset to a near-full-frame **1864×806** arena inside the existing 1920×1080 presentation.
- Three contract-specific authored layouts now use reusable prefab pieces: short/long walls, L-corners, broken corners, pillars, archive stacks, relic carriages, shrines, brittle cover, and visible reinforcement gates.
- Separate physical objects must maintain at least **120 px** of clearance; validation also checks live actor/spawn marker spacing and routes using the **36 px signature-boss radius**.
- Solid-looking prefabs block movement, projectiles, and line of sight from the same geometry. Decorative floor markings remain explicitly non-colliding.
- Brittle wall prefabs have real integrity. Projectile impacts and Ash Saint rupture pressure can crack and destroy them. A destroyed wall becomes visible rubble and immediately stops blocking navigation, sight, and fire.
- Navigation cache is invalidated when cover is breached, allowing autonomous heroes/enemies to use newly opened routes.
- Reinforcement gates are visible floor devices with protected emergence clearance but intentionally do not become invisible blockers.
- Each contract has its own material textures under `assets/world/` so physical cover reads as Saint Voltage masonry/reliquaries, Blackglass slabs/archive structures, or Ossuary transit/carriage construction.

### Permanent world rule

**If it looks solid, it is solid. If it affects navigation, its visible shape explains why. If it is only decoration, it must read as floor/surface decoration.**


## Pass 15 actor identity foundation

- Heroes retain their established identities and portraits, but remaining line-like legs are replaced with filled armored/cloth limbs and real boot forms.
- Revenants, constructs, and cantors have complete body volumes with filled limbs, equipment, heads/masks, and contract livery attached to the body.
- The Ash Saint, Mirror Abbot, and Last Conductor each receive unique sovereign-scale body geometry instead of relying primarily on aura/effect enlargement.
- Archive Pilgrim, Choir Defector, and Relic Medic civilians now have different costumes, headgear, carried gear, panic reads, and rescued reads.
- Presentation footprints are bounded separately from simulation collision. The largest sovereign visual diameter is **98 px**, below Pass 14's **120 px** minimum world-object gap, leaving **22 px** of visual margin.
- `game/sim.py`, `game/data.py`, `game/world.py`, and `game/world_data.py` remain byte-for-byte identical to Pass 14.

### Permanent actor rule

**A gameplay role must read from body shape, equipment, and motion before the player needs a label. Presentation can become richer without silently changing collision or combat authority.**

## Final balance identity

The roster is deliberately asymmetric:

- **NYX-7** leads direct purge speed and can force prepared off-role victories at substantial risk.
- **Brother Circuit** is the safest protector and strongest rescue anchor.
- **Vesper Coil** is the low-strain Blackglass specialist and precision support operative.
- **MORROW-9** uses defeated enemies as temporary echoes that now absorb real hostile pressure; MORROW leads fast rescue routing but remains vulnerable to corruption and collapse.

Every hero is viable. Every contract has multiple credible choices. Equipment, orders, and HEX Links can recover difficult matchups, but poor unprepared assignments can still fail.

## Controls

### Front end

- **Enter / C:** continue from title
- **S:** settings from title or contract board
- **H:** field guide
- **N twice:** start a new guild profile
- **F11:** borderless desktop / 1280×720 windowed toggle (native 1920×1080 canvas is unchanged)
- **Esc:** back; return to title; quit from title

### Contract flow

- **LMB:** select contracts, heroes, orders, equipment, Sidekicks, bond outcomes, actors, or restoration targets
- **RMB:** back or close dossier
- **O:** cycle guild order
- **R:** medbay recovery
- **E:** cycle equipment
- **B:** cycle Sidekick team
- **Enter:** prepare, deploy, acknowledge results, or trigger Last Light
- **Tab:** decision analysis
- **I:** actor dossier
- **Space:** pause

## Run

```bash
python main.py
```

## Key verification commands

```bash
python -m py_compile main.py game/*.py tools/*.py
python main.py --quick-test --no-audio
python main.py --pass10-test --no-audio
python main.py --pass11-test --no-audio
python main.py --pass12-test --no-audio
python main.py --pass13-test --no-audio
python main.py --pass14-test --no-audio
python main.py --pass15-test --no-audio
python main.py --pass16-test --no-audio
python tools/pass16_presentation_verify.py
python tools/pass17_visual_verify.py
python tools/pass17_world_preview.py
python main.py --pass15-test --no-audio
python tools/pass14_world_verify.py
python tools/pass14_verify.py
python tools/pass15_actor_verify.py
python tools/pass13_balance.py
python tools/pass13_endurance.py
python tools/pass13_verify.py
```

Pygame is the game engine. Panda3D is used only to confirm that exported 1920×1080 proof images can be decoded and measured independently.

## Pass 15 verification note

`tools/pass15_actor_verify.py` is dependency-free and validates that the gameplay/world authority remained byte-identical, the new body helpers and role-specific actor contracts are present, and the maximum actor presentation footprint remains compatible with Pass 14 spacing. `python main.py --pass15-test --no-audio` requires pygame-ce 2.5.7 and renders live actor bounds. `tools/panda_verify.py` remains the independent Panda3D image-readability gate for exported proof PNGs.

## Pass 20 multiple approved broken-maze layouts

Pass 20 turns each Pass 19 battlefield into a small approved layout pool instead of a single fixed arrangement.

- **3 layouts per contract / 9 approved layouts total.**
- Variant 1 is the exact Pass 19 canonical layout.
- Variants 2 and 3 remix object position/facing inside the same broken-maze grammar.
- Every variant preserves the same contract markers, setpiece identities, access-break labels, 120 px minimum obstacle gap, and 36 px maximum actor requirement.
- Every required enemy, civilian, boss, objective, complication and extraction route remains reachable before any destructible cover is broken.
- Layout selection is deterministic from the mission seed; normal campaign replay advances the layout using the existing per-contract aftermath count, while failed retries retain the current layout until that count changes.
- Combat balance tables, AI data, hero/enemy definitions, audio and renderer behavior are unchanged.

### Pass 20 verification

```bash
python tools/pass20_multi_layout_verify.py
python tools/pass20_layout_preview.py
```

The dependency-free validator covers all nine layout variants and writes `verification/reports/pass20_multi_layouts.json`. Fresh proof images are written under `verification/screenshots/pass20/`.

## Pass 23 — Platform Achievement Foundation

HEX CONTRACT now includes a platform-neutral 16-achievement / 1000G launch set designed for Xbox title-managed Achievements. Achievement progress is persistent and monotonic, real gameplay events feed the tracker, and nine-layout wins are now recorded for `Every Way Through`. The portable source build does not require Xbox GDK libraries; `AchievementTracker.sync_pending()` is the native bridge seam for a future Windows GDK wrapper. Partner Center staging files are under `platform/xbox/`.
## Pass 25 — Microsoft Full-Title Packaging + Save Preparation

Pass 25 adds a non-demo Microsoft/GDK packaging staging layer under `platform/microsoft/`. It does not add fake Partner Center identity values and does not place a placeholder `MicrosoftGame.config` at the game root. Use the included stage generator only after a Windows x64 runtime and real Partner Center identity values exist. The existing profile remains schema v9 and is ready to be routed to the folder returned by XGameSaveFiles.


## Pass 26 — Windows Full-Title Runtime + Native GDK Acceptance

Pass 26 turns the Pass 25 staging contract into an executable Windows build path and a real native Xbox-services boundary. `platform/windows/BUILD_WINDOWS_FULL_TITLE.bat` produces a clean pygame-ce onedir runtime on Windows; `platform/microsoft/native_bridge/` contains the optional GDK DLL source for user sign-in, XGameSaveFiles and title-managed achievement updates; `tools/pass26_prepare_gdk_stage.py` refuses to stage the Microsoft package until both `HEXContract.exe` and `HEXContractGDKBridge.dll` exist alongside real Partner Center identity.

The source/Prototype Lab build remains portable. A frozen non-GDK Windows runtime stores fallback saves under `%LOCALAPPDATA%\GLITCHED MATRIX\HEX CONTRACT`; a real Microsoft package overrides that with the XGameSaveFiles `HEXContract` container. The bridge reacquires XGameSaveFiles on restore/focus return before continuing saves.

Native acceptance is deliberately not self-certifying: install the `/lt` MSIXVC with `wdapp install` and run `platform/microsoft/native_acceptance/RUN_NATIVE_ACCEPTANCE.ps1`. Only a real Windows/GDK/controller/Xbox-services session can produce a PASS report.


## Pass 32 finalization fixes

- Music volume is independent of SFX. Music 100% now means full music output under Master volume.
- Final routed music is mastered to approximately -16 LUFS.
- Settings volume rows have explicit mouse minus/plus controls and 5% keyboard/controller steps.
- ESC/Menu opens a real mission pause menu with Resume, Settings, and confirmed Abort. It no longer destroys an active mission immediately.
- Windows builds stage/test outside `windows_dist` and publish the final folder only after all packaged tests pass. A successful build leaves `HEXContract.exe`, a portable ZIP, and `BUILD_SUCCESS.txt` in `windows_dist`.
