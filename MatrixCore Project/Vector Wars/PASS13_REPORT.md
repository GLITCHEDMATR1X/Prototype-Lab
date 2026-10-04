# Vector Wars Pass 13 — Campaign Persistence Authority

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING — pygame-ce unavailable in current container
TARGET-RUNTIME TEST: NOT RUN

## Single target
Persist the campaign-owned phase and operation progress without expanding combat, audio, difficulty, or UI.

## Changes
- Added `campaign_save.py` with schema-versioned JSON campaign saves.
- Save location reuses the existing per-user Vector Wars data root (`LOCALAPPDATA`/`APPDATA` on Windows; XDG user data on Linux).
- Ground street/Giant progress, Air fighter/UFO progress, Ocean warship/helicopter progress, active campaign phase, and final completion state are persisted.
- Save writes use a same-directory temporary file followed by `os.replace`.
- Relaunch restores campaign progress and returns to the campaign-owned combat front.
- Later-phase saves enforce completed earlier phases so corrupted/incomplete cross-phase state cannot reopen an already-cleared front.
- Invalid, corrupt, or incompatible save data falls back to a fresh campaign rather than blocking launch.
- Campaign replay clears the campaign save before the existing fresh-process restart.

## Explicitly not persisted
- player hull/shield
- destroyed buildings/world geometry
- enemy positions or temporary deaths
- projectiles/explosions/fires
- temporary timers/weather state
- developer mode

Those are deliberately excluded so this pass does not become a world-state serialization project.

## Regression
Pre-edit: 14/14 PASS.
Post-edit/fresh source tree: 16/16 PASS.
New checks cover save round-trip, phase invariants, corrupt-save fallback, replay clearing, atomic replacement contract, and user-data location.

## Reference
Python documents `os.replace()` as the cross-platform overwrite-capable replacement operation, with successful same-filesystem replacement atomic on POSIX. This is the basis for the temp-file replacement pattern used here.

## Runtime acceptance still required
1. Start Ground, earn partial progress, quit, relaunch, confirm counts restore.
2. Complete Ground, enter Air, quit, relaunch, confirm Air resumes.
3. Earn partial Air progress, quit/relaunch, verify restoration.
4. Enter Ocean, earn partial progress, quit/relaunch, verify restoration.
5. Complete campaign, quit/relaunch, verify victory state resumes.
6. Press ENTER at campaign completion and confirm a fresh Ground campaign starts with zero progress.
7. Corrupt `campaign_save.json` manually and confirm launch falls back cleanly to new Ground campaign.
8. Confirm no new HUD overlap or pause/input regression at 1920x1080.
