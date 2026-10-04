# Vector Wars Pass 14 — HUD Hierarchy + Objective Readability

STATUS: CANDIDATE  
VISUAL ACCEPTANCE: PENDING — pygame-ce unavailable in current container  
TARGET-RUNTIME TEST: NOT RUN

## Task
Clean the campaign HUD/objective presentation without changing gameplay.

## Reference basis
- Microsoft Xbox Accessibility Guideline 101 (Text display): readable PC HUD text, minimum 18 px at 1080p, spacing, readable case, and configurable/readable presentation.
- Microsoft Xbox Accessibility Guideline 102 (Contrast): important UI needs sufficient foreground/background contrast.
- Existing GX Prototype Lab rule: one owner per HUD safe zone; visible regressions outrank feature work.

## Changes
- Added `hud_layout.py` as a pure-Python authority for mission copy and top-level HUD bands.
- Mission display is now two-level: short uppercase phase label + sentence-case action/progress line.
- Mission text keeps the existing 18 px gameplay font minimum and receives a dark translucent backing.
- Removed stale prototype wording such as `PHASE AWAITS` / `PHASE RELEASED` from normal mission presentation.
- Moved temporary weapon/vehicle-change banner out of the mission coordinates.
- Moved F3 diagnostic lines below temporary notification bands.
- Removed the duplicate center-screen DEV label; DEV remains visibly owned by the footer.
- Updated Field Guide mission wording to reflect the actual Ground -> Air -> Sea campaign.
- No combat, progression, save, balance, audio, or HoloVerse behavior changed.

## Regression discovery/fix
The old weapon-change banner used y=12/18, the same top-center region as the mission objective. This guaranteed overlap whenever that banner appeared. Pass 14 gives the two systems separate bands.

Four older regression tests were updated because they hard-coded the previous one-line `objective_text()` rendering path. Their gameplay checks were preserved and the new HUD authority is now explicitly tested.

The Pass 04 TAB test was also tightened to verify the actual `if dev_mode ...` gate around TAB rather than merely looking for `dev_mode` elsewhere in the file.

## Verification
`python tools/run_regressions.py`  
`run=17 pass=17 fail=0`  
`VECTOR_WARS_REGRESSIONS: PASS`

`python -m py_compile main.py hud_layout.py tools/test_pass14_hud_hierarchy.py`  
PASS

Static HUD-zone contract:
- mission: y 10–72
- temporary notice: y 82–108
- weapon notice: y 114–146
- diagnostics: y 150–246
- footer: y 1052–1080
- top-level bands overlap: NO

`verification/Pass14_HUD_SafeZone_Proof.png` is a schematic coordinate proof, not a Pygame runtime screenshot.

## Runtime acceptance still required
1. Confirm mission backing/contrast over Ground, Air, and Ocean motion.
2. Confirm weapon-change banner never covers mission copy.
3. Confirm temporary transition notices remain readable.
4. Confirm F3 diagnostics do not collide with other HUD content.
5. Confirm footer remains readable in DEV and normal mode.
6. Check full-screen and bordered/windowed presentation.
