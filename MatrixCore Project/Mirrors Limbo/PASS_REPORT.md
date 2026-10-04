# Mirror's Limbo — Pass 151 Report (Linked Worlds)

STATUS: CANDIDATE
TARGET-RUNTIME TEST: PASS (Linux, Xvfb real windows + offscreen suites); Windows 11 player acceptance pending

## Single target
Finish the DreamCatcher / Andrew's Nightmare integration so both play as parts of Mirror's Limbo.

## Implemented
- One shared runtime package, `gx_common/` (travel, shared settings + progress, QA harness). It replaces 3 diverged copies of `gx_travel.py`, 3 of `gx_travel_qa.py` and 2 of the unused `dreamcatcher_bridge.py`.
- Discovery uses the fixed layout inside Mirror's Limbo (no Lab-wide scan, no `gx_lab.json` needed; stray copies elsewhere can't be picked up).
- The window restore after travel only puts back the cursor state it changed (Andrew's fix, now used by all three games).
- The source window stays visible behind a black loading cover until the destination is ready (no desktop gap; the new window is allowed to take focus). Exclusive fullscreen still minimizes.
- Travel session folders are pruned (newest 8 kept, nothing older than 2 days).
- DreamCatcher finale: Esc (or 10 s) wakes the player in Limbo instead of quitting to the desktop. The completion is recorded.
- Andrew: breaking the intercept records the ending and enables Q without pausing. The Null-Layer disconnect records its ending and returns to DreamCatcher automatically.
- DreamCatcher house progress persists across trips to Andrew, trips to Limbo and quitting. It is cleared after the finale.
- The Limbo TV menu shows linked completions.
- DreamCatcher and Andrew follow Limbo's settings: sensitivity, invert-Y, master volume, display mode, resolution, v-sync, and FOV as an offset from each world's default. Changes made in those worlds write back to Limbo.
- HoloVerse-embedded Limbo no longer offers DREAMCATCHER (switching would have closed the host).

## Validation
- Chain A: Limbo → DreamCatcher (house progress made) → Andrew (intercept broken, Q) → DreamCatcher (exact house state restored; finale; Esc) → Limbo (completions shown, house cleared): PASS.
- Chain B: Limbo → DreamCatcher → Andrew → DreamCatcher → Limbo → DreamCatcher → Limbo: house restored on both returns; all previous processes exit.
- Shared settings: Limbo sensitivity 0.10 / FOV 80 / windowed 1600x900 gave DreamCatcher 0.10 / FOV 84 / windowed 1600x900 and Andrew 0.10 / FOV 96 / windowed.
- Missing destination: travel fails cleanly, and the source is un-paused and has its input restored.
- Loading cover: hides the paused menu and is removed when travel fails.
- Limbo `--smoke-test`, `--pass149-test`, `--mirror-test`: PASS.
- DreamCatcher `--compat-check`, finale / bridge / lore test shots, `tools/verify_*`: PASS.
- Andrew `--self-test`: PASS. `tools/verify_build.py`: the same 3 pre-existing failures as the unmodified build (the PASS17 plan/report docs are not in the package).

## Needs the Windows machine
- Focus and cursor capture after each switch, real audio volume, F11/display changes, and the launchers.
- If the Steam build starts games through the bundled `py_runner`, confirm that it accepts a script path. Travel relaunches `sys.executable <world entry>.py`.

---

# Mirror's Limbo — Pass 149 Report

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PASS (native Panda3D 1.10.16 software renderer)
TARGET-RUNTIME TEST: PASS (Linux/Xvfb/Mesa); Windows player acceptance pending

## Single target

Delay the TV/Framework path until the first genuine return to Limbo, and eliminate the remaining stair-to-patio support seam reported from the real Windows build.

## Research -> decision

Panda3D's floor handlers are built around sampling a floor height beneath the avatar, and Panda3D community character-controller guidance describes continuous ramp collision as the common solution for visually stepped stairs. Panda's documentation also warns that floor-following can slip on sloping paths when motion/sampling are poorly conditioned. The practical consequence for this controller is to provide a continuous ramp plus a flat top landing large enough for the player capsule rather than letting the floor transition exactly on the patio face.

Progression research likewise supports staggering mechanics/environmental rewards after the player has learned the initial loop rather than exposing every system immediately. Pass 149 therefore uses the first semantic Alt-Limbo return as the TV discovery event.

References:
- https://discourse.panda3d.org/t/raycast-character-controller-handling-stairs/14050
- https://docs.panda3d.org/1.10/python/reference/panda3d.core.CollisionHandlerFloor
- https://docs.panda3d.org/1.10/python/programming/collision-detection/rapidly-moving-objects
- https://www.gamedeveloper.com/design/gameplay-design-fundamentals-gameplay-progression

## Implemented

- Fresh cycle-0 Limbo has no TV system instantiated.
- TV discovery persists as `tv_discovered` (save schema v12).
- Only `house_return` and `fear_return` can perform first discovery.
- Old saves with cycle >= 1 migrate to discovered TV.
- TV collision cache is rebuilt when the TV appears mid-session.
- Pass 148 ramp now reaches full deck height one player-radius before the patio edge.
- 0.80 m flat top landing bridges capsule clearance across the deck face; 0.38 m continues beneath the patio.
- Mirrored realm uses the exact mirrored semantic ramp.
- Debug view marks the incline-to-landing transition.

## Native validation

- Pass 149 progression + stair test: PASS
- Initial TV state: absent mesh/anchor/collision/light/audio owner
- Non-return unlock attempt: blocked
- First semantic return: TV built and collision cache updated
- Stair/deck seam dwell matrix: 24/24 continuous
- Stair route matrix: 120/120 reached (walk, sprint, 20 Hz sprint, diagonal, descent; normal + mirror)
- Inherited Mirror/VOID/TV-world runtime contract: PASS
- Fresh cycle-0 smoke: PASS
- Post-return save/reload smoke: PASS; TV restored
- Same-camera 1080p TV before/after visual proof: PASS
- Stair clean/collision 1080p proof: PASS

## Known inherited warning

Panda3D's Linux FFmpeg path still logs one `bad src image pointers` warning when the H.264 TV movie initializes. The accepted source video is unchanged.
