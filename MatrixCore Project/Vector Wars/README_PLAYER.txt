VECTOR WARS — itch.io RC1.2

Deploy across AIR, GROUND, and OCEAN combat fronts in a procedural neon warzone.

START
Run VectorWars.exe and choose the bordered or windowed launch option.

CORE CONTROLS
Mouse or A/D  Yaw
W/S           Pitch
Q/E           Roll
Shift         Boost
Space/Ctrl    Hover / rise / descend / brake
LMB           Primary weapon
RMB           Missile / torpedo
R             Cycle weapon mode
T             Cycle target
V             Cycle vehicle
F4            Toggle developer mode
TAB           Change combat front (developer mode only)
F1            Field Guide
F2            Mouse lock
F3            Diagnostics
M             Mute / restore audio
- / +         Lower / raise master audio
, / .         Lower / raise SFX
[ / ]         Lower / raise music
F11           Fullscreen
ESC           Quit confirmation

GROUND OPERATION
Break the street assault, then destroy a Giant. Securing the phase fully repairs and resupplies your current vehicle.
AIR and OCEAN now have finite operation loops. F4 developer mode remains available for direct front testing.

AUDIO
Packaged SFX are verified during the Windows build. Audio starts below full volume.
GROUND, AIR, and OCEAN each have three original procedural placeholder music loops.
The nine tracks are asset-driven and intended to be replaced later without changing gameplay code.
Custom phase music can be placed in custom_audio/music/ground, /air, or /ocean.
Music and SFX can be adjusted independently.

PLAYER DATA
Writable files are stored under:
%LOCALAPPDATA%\GLITCHED MATRIX\Vector Wars

STATUS
Early access prototype candidate. Keyboard and mouse required.

PASS 05 GROUND FAILURE / REDEPLOY
- In Ground combat, losing the player unit no longer creates an immediate replacement.
- ENTER redeploys at the operation insertion point with a fresh unit.
- Ground objective progress is preserved across redeployment.
- Developer TAB front switching is temporarily blocked while a Ground redeploy is pending.

PASS 06 GROUND → AIR PROGRESSION
- Completing the Ground operation now advances normal play into AIR.
- The transition preserves the existing Air combat implementation; no Air mission design has been added yet.
- F4 developer mode can still test fronts with TAB, but leaving developer mode restores the campaign-owned phase.

CAMPAIGN PROGRESSION
- Normal play begins on the Ground front.
- Securing Ground advances to Air.
- Securing Air advances to the Maritime/Ocean front.
- F4 enables developer testing mode; TAB changes fronts only while developer mode is active.

PASS 09 AIR OPERATION
- Establish air control by defeating hostile fighters, then intercept UFO contacts.
- Air completion repairs/resupplies the current craft and releases the Maritime phase.

PASS 11 OCEAN OPERATION
- Break the hostile surface action group by sinking 4 warships.
- Defeat 2 maritime-strike helicopters.
- Sea-control completion repairs hull and shields.
- Exact target counts are gameplay tuning; naval terminology is reference-informed.

PASS 12 CAMPAIGN LOOP
- Normal progression is GROUND -> AIR -> OCEAN.
- Completing Ocean finishes the three-front campaign.
- ENTER at the campaign-complete state starts a completely fresh replay.
- F4 remains developer mode; TAB front switching is available only while developer mode is active.

PASS 13 CAMPAIGN PERSISTENCE
----------------------------
- Campaign phase and objective progress are saved automatically after confirmed player-attributed objective kills and phase transitions.
- Saves live in the per-user Vector Wars data directory, not inside the installed game folder.
- Relaunching resumes the current campaign phase and operation progress.
- A corrupt or incompatible campaign save falls back to a fresh campaign instead of blocking launch.
- ENTER from CAMPAIGN COMPLETE explicitly clears the campaign save before starting a fresh replay.
- World destruction, enemy positions, player hull/shield, and temporary combat objects are intentionally not persisted in this pass.

PASS 14 HUD / OBJECTIVE READABILITY
-----------------------------------
- Mission HUD now uses a short phase label plus a sentence-case objective/progress line.
- Mission text has a dark translucent backing for readability over combat backgrounds.
- Weapon/vehicle-change notices, diagnostics, and mission text now use separate HUD bands.
- Developer state remains visible in the footer without a duplicate center-screen label.

PASS 15 PHASE MUSIC AUTHORITY
-----------------------------
- Three replaceable music tracks are assigned to each campaign phase: Ground, Air, and Ocean.
- Phase changes switch the active soundtrack pool automatically; F4/TAB developer front testing switches the music pool too.
- Player-owned phase folders override the shipped pool for that phase without modifying the install.
- Music volume is re-applied after each track load so rotation cannot jump to full volume.
- ,/. adjust SFX only; [/] adjust music only; -/+ remains master audio.
- HoloVerse can still suppress Vector Wars music when the host owns the music bus.

PASS 16 COMBAT DIFFICULTY AUTHORITY
-----------------------------------
- Graphics/performance presets no longer change the number of active combat threats.
- Standard combat population preserves the previous default Smooth experience: 30 street threats, 10 fighters, 3 UFOs, 5 warships, and 2 helicopters.
- Performance presets remain responsible for rendering/object budgets, not hidden difficulty changes.
- This pass establishes a stable balance baseline before later vehicle-speed, weapon-pressure, and difficulty-option tuning.

HOLOVERSE LEGACY / EXTERNAL CONTRACT
------------------------------------
- Normal HoloVerse launch resumes the campaign-owned phase; it does not force an AIR QA start.
- --auto-mode air/foot/ocean remains an explicit developer/QA override only.
- HoloVerse should suspend its host reality, launch Vector Wars as a child process, wait for exit, then restore the host state.
- --holoverse-launch enables HoloVerse return wording while keeping Vector Wars in its own Pygame process.
- The child shuts down its own Pygame display/mixer on exit before the host resumes.
- HOLOVERSE_ROOT_OWNS_MUSIC can suppress child music; HOLOVERSE_SHARED_SFX_DIR can provide shared SFX.
- VECTOR_WARS_USER_DATA can redirect player-data storage when the host needs an explicit shared location.
- This is intentionally LEGACY/external compatibility, not a claim of same-window Panda3D-native rendering.
