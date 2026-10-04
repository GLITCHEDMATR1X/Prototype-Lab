# Gleebs Protocol: HoloTactics — Pass 30 HUD Alignment Redo

A Panda3D futuristic turn-based tactics prototype set inside the HoloVerse style.

## Current status
Pass 30 rebuilds the player HUD from the accepted Pass 29 base. The normal HUD is aligned to shared edge/padding rules and keeps only player-facing tactical information. Developer diagnostics are hidden by default behind F9. Gameplay, objectives, AI, actors, audio, progression, and HoloVerse adapter behavior are unchanged.

## Standalone requirements and first run
- Python 3.12 or 3.13 recommended (tested here with Python 3.13.5)
- Panda3D 1.10.16

From this folder:

```text
python -m pip install -r requirements.txt
python main.py
```

On Windows, after installing the requirements, `run_game.bat` launches the game from the correct project directory. No NumPy, Pillow, glTF plug-in, or external media package is required by HoloTactics itself.


## Focus of this pass
- Rebuild the misaligned Pass 30 HUD from the accepted Pass 29 package rather than patching the rejected branch.
- Align left/right HUD columns to shared edges and consistent internal padding.
- Keep the normal HUD minimal: selected squad state, primary mission state, comms, and core controls.
- Put developer/runtime diagnostics exclusively behind `F9` and keep that overlay hidden by default.
- Preserve the complete Pass 29 gameplay core unchanged.

## Current loop
1. Start the simulation.
2. Destroy hostiles when useful; some may drop one-shot abilities.
3. Move a squad unit onto an ability pickup to recover it.
4. Press `X` with a unit selected to spend the currently loaded one-shot ability at the cursor.
5. Sector 1 / Archive Gate: move Gleebs to the Memory Node, then break the Game Master Core.
6. Sector 2 / Signal Causeway: synchronize both Signal Relays with any squad units; the Route Lock then collapses automatically.
7. Sector 3 / Fracture Expanse: move Gleebs adjacent to the three Fracture Anchors and use `Q` Patch Pulse to stabilize them in any order; the Stability Gate collapses automatically.
8. Sector 4 / Outer Signal Grid: split the squad across both Outer Uplinks and hold them through two hostile response cycles.
9. Sector 5 / Matrix Horizon: align both Horizon Relays, use Gleebs Patch Pulse on the exposed central Horizon Fracture, then occupy both relays through one hostile response cycle to collapse the Matrix Horizon Core.
10. Reach the Extraction Gate.
11. Press `N`, `C`, `Enter`, or `LMB` after sealing a sector to expand the route if another sector is available.

## Bigger journey route
1. Archive Gate — 8x8 board — Threat LOW
2. Signal Causeway — 10x10 board — Threat RISING
3. Fracture Expanse — 12x12 board — Threat FOCUSED
4. Outer Signal Grid — 14x14 board — Threat WIDE
5. Matrix Horizon — 16x16 board — Threat HORIZON

## Ability system preserved
Destroyed enemies can randomly drop one-time-use ability fragments. Current procedural families:

- **Arc** — ranged one-shot damage against a hostile target.
- **Patch** — stabilizes nearby corrupted/fracture tiles and restores nearby ally HP.
- **Blink** — repositions the selected unit to an empty board tile within range.
- **Snare** — damages and slows a hostile target while creating a fracture effect.

Abilities remain one-time use and the cache remains capped to 3 for readability.

## Controls
- Enter / Space / LMB: start, select, or continue the journey after sector clear
- WASD / Arrow keys: cursor
- LMB: target/select/move
- RMB / F: attack
- M: move selected unit
- Q: Gleebs Patch Pulse
- X: use loaded one-shot ability
- E: end turn
- N / C: continue route after a sector is sealed
- H: hide/show HUD
- J: open/close Journey Map
- F9: toggle developer diagnostics (hidden by default)
- V: mute/unmute SFX
- B: mute/unmute music
- R: reset to title
- ESC: pause / resume (standalone); shared HoloVerse menu/return flow when hosted

## Notes
The normal HUD intentionally excludes round counters, threat/pulse percentages, synchronization percentages, audio diagnostics, board dimensions, and runtime state. Those values live in the F9 developer view so the player-facing screen stays minimal.


## Pass 15 note
This pass fixes Windows/Panda3D audio path loading. The game was already generating the WAV files, but Panda3D can reject raw Windows-style strings. SFX/music paths are now normalized before loading so assets under `assets/sfx` and `assets/music` can load correctly from a Windows install path.


## Pass 16 — HoloVerse Full-Source Native Compatibility

HoloTactics can now be linked by selecting this project's real `main.py` in Gleebs' Dimension Archive. HoloVerse 278+ mounts the complete game into its already-open Panda3D ShowBase/window instead of creating a second window or a replacement tactical scene.

Native linked behavior:
- same Windows window and ShowBase
- HoloVerse display/fullscreen/VSync/UI/HUD/graphics settings remain authoritative
- HoloTactics SFX/music use HoloVerse master/music/SFX volume policy
- the real five-sector tactical journey, UI, actors, abilities and controls are preserved
- `TAB` returns immediately to HoloVerse
- `ESC` uses the shared HoloVerse menu/return flow
- standalone `python main.py` remains supported

No HoloTactics gameplay content was replaced with host-side placeholder geometry.


## Pass 17 — Standalone Control & Pause Safety

This pass changes only standalone pause/control behavior. `ESC` no longer terminates the game immediately. It opens a modal pause screen with Resume, Restart Journey, Controls, SFX, Music, and Quit to Desktop. Gameplay input is blocked while the pause modal owns input. Restart and Quit require a second confirmation. HoloVerse-hosted `ESC`/return ownership is unchanged.


## Pass 18 — Large-Board Targeting Audit/Fix

This pass changes only mouse targeting certainty on the large tactical boards. The existing board geometry, objectives, AI, progression, and actor art are unchanged. Mouse-to-board projection now derives the picking plane from the board NodePath itself rather than assuming a world-aligned board, and the tile currently under the pointer receives a lightweight pre-click frame highlight without moving the tactical cursor. Sector 4 (14×14) and Sector 5 (16×16) are the required regression targets.

## Pass 19 — Tactical Readability

This pass changes only tactical-state readability. Existing board geometry, AI, objectives, progression, actor art, and combat rules are unchanged.

Tactical state now uses both color and geometric cues:
- legal movement: green tile treatment + center diamond
- attack range: orange range treatment + X marker
- selected unit: cyan ring beneath the selected piece
- keyboard/current target: explicit cyan tile frame; mouse hover remains yellow
- corrupted/fracture danger: persistent corner-bracket hazard marks
- current mission objective: one bright objective bracket on the active required node
- loaded ability: compact +/diamond cue on the current cursor when that tile is a valid target; valid mouse-hover targets use a purple focus frame

The bottom help strip includes a compact cue legend. No new tutorial panel was added.


## Pass 20 — Enemy Tactical AI

This pass changes only enemy decision-making. Board geometry, objectives, player controls, actor art, progression, damage values, and unit rosters are unchanged.

- **Debug Hunter / Anomaly:** recognizes mandatory objective pressure, then vulnerability and distance; when advancing it breaks equal-distance ties by avoiding unnecessary clustering with other hostiles.
- **Ranged Firewall / Sentry:** uses its existing two-tile attack range as a preferred firing envelope. It backs away from point-blank contact when an open retreat tile exists, fires when already at useful range, and advances toward a firing lane when too far away.
- Enemy targeting is recalculated before each hostile acts, so a unit defeated earlier in the same phase is not targeted again.
- Decisions remain deterministic so identical tactical states produce identical enemy choices.


## Pass 22 — Sector 3 Objective Identity

Fracture Expanse now uses its existing hazard language as the mission itself. Three persistent Fracture Anchors are distributed across the 12x12 board. Gleebs must get adjacent to each anchor and use Patch Pulse (`Q`) to stabilize it. The anchors may be handled in any order. Walking onto an anchor remains hazardous and does not count as stabilization. Once all three anchors are stable, the Stability Gate collapses automatically and Extraction opens. Sector 1 and Sector 2 objective structures are unchanged.

## Pass 23 — Sector 4 Objective Identity

Outer Signal Grid now uses the 14x14 board width as the mission itself. Two far-separated Outer Uplinks must be occupied simultaneously by living squad units and held through two hostile response cycles. Any squad members may form the link. If either uplink becomes unoccupied before the bridge stabilizes, progress resets. Once both cycles succeed, the Grid Bridge Lock collapses automatically and Extraction opens. The lock cannot be attacked directly. Sectors 1–3 retain their existing objective identities.

Design reference: Game Developer, “The Balance of Power: Progression and Equilibrium in Real-Time Strategy Games” — its control-point discussion specifically notes that multiple objectives force proactive movement and splitting forces across the map.


## Pass 24 — Sector 5 Finale

Matrix Horizon is now a three-stage final mission built only from tactical language already taught earlier in the journey:

1. **Align** — any squad units may visit the two distant Horizon Relays in either order.
2. **Stabilize** — alignment exposes the central Horizon Fracture; Gleebs must get adjacent and use Patch Pulse (`Q`).
3. **Hold** — after stabilization, living squad members must occupy both Horizon Relays simultaneously and survive one hostile response cycle.

Completing the hold collapses the Matrix Horizon Core automatically and opens the final Extraction Gate. The Core cannot be bypassed with a direct attack.

Design references: Game Developer, “Building Better Bosses” (multi-stage end encounters can re-evaluate skills learned throughout the game) and the Into the Breach final-mission interview (a finale can build on the rest of the game through multiple stages rather than only increasing raw difficulty).


## Pass 25 — Journey Map

Press `J` to open a read-only five-sector route view. The map is derived from the actual campaign state and labels each destination as `SEALED`, `CURRENT`, or `LOCKED`, along with board size and threat label. It does not select sectors, skip progression, or alter mission state. Tactical input is blocked while the route view is open; `J` closes it and standalone `ESC` closes it before opening the pause menu.

Design references: Game Developer, “Polishing a Level Select screen: process and implementation” (make current goal/unlocking state clear with distinct locked/unlocked/current states and visible paths) and “Level Design Lesson 12: Path Maps” (route/goal relationships are the information a path map should communicate).


## Pass 26 — Actor Visual Upgrade

This pass changes only the procedural board pieces. The design is silhouette-first: Gleebs keeps the tall paired ears and cyan/red orb identity from the supplied reference; Fracture Guard reads as a broad shield-bearing anchor; Phase Runner uses a narrow forward spear/fins silhouette; Corrupted Anomaly uses asymmetric shard/blade forms; Rule Sentry uses a floating sensor core, long barrel and swept fins.

The actors remain generated directly through Panda3D geometry and preserve the established tactical footprint/height limits. Gameplay logic and actor stats are unchanged.

## Pass 27 — Sector Audio Identity

Each journey sector now owns one restrained ambient loop instead of sharing one generic track:

- Sector 1 / Archive Gate — sparse archive pulse
- Sector 2 / Signal Causeway — quicker signal cadence
- Sector 3 / Fracture Expanse — unstable/dissonant fracture bed
- Sector 4 / Outer Signal Grid — broad low grid pulse
- Sector 5 / Matrix Horizon — deeper, faster finale pressure

The music system keeps exactly one sector loop active at a time. `B` still toggles music globally, and unmuting resumes the current sector's track rather than reverting to Sector 1.


## Pass 28 — Native Input Authority Hardening

The native adapter no longer registers HoloTactics standalone key bindings on HoloVerse's global Panda3D Messenger. Hosted gameplay input is accepted only through the host action bridge; ESC/TAB/menu/return remain host-owned. Host camera FOV is snapshotted as immutable numeric values and restored exactly on return. A Panda3D host harness exercises three enter/return cycles and checks same-window use, host task survival, input ownership, camera/lens/background restoration, source-scene cleanup, and audio handoff. Actual HoloVerse-build acceptance remains pending until a current HoloVerse package is supplied.


## Pass 29 — GXTool Contract Cleanup

This pass changes packaging/dependency authority only. Audio cue specs now store the same project-relative asset paths that runtime loading uses, eliminating false root-level missing-asset reports. The optional GXTool smoke hook is imported dynamically only when a GXTool runtime provides it, so ordinary users do not need `runtime_hooks`. `requirements.txt` pins Panda3D 1.10.16 for standalone source installs.
