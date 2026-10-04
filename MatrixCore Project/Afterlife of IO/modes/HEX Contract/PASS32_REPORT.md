# HEX CONTRACT — Pass 32: Finalization UX / Audio / Windows Build Fixes

## Scope

Pass 32 is a finalization-blocker repair pass built from Pass 31.1. It does not add contracts, heroes, enemies, achievements, layouts, or balance changes.

## Confirmed problems repaired

### 1. Music remained too quiet at 100%

Pass 31.1 still calculated music gain by clamping `music_volume` against `sfx_volume`. As a result, the Music slider was not a truly independent control. The five final loop tracks were also mastered around -20 LUFS.

Pass 32:

- removes the hidden SFX clamp from music gain;
- makes Music 100% equal to full music output under Master volume;
- keeps fresh-profile defaults slightly SFX-forward: Master 85%, SFX 85%, Music 75%, Ambience 45%;
- remasters the five already-trimmed loop assets to approximately -16 LUFS;
- preserves the deterministic main / Purge / Recovery / Rescue / Sovereign routing and infinite looping.

Measured final integrated loudness:

- MCF12: -16.1 LUFS
- MCF18: -16.0 LUFS
- MCF22: -16.0 LUFS
- MCF26: -16.0 LUFS
- MCF28: -15.9 LUFS

### 2. Volume controls felt broken

Mouse input on a settings row previously only advanced the value. There was no mouse-visible decrease control.

Pass 32 adds explicit `-` and `+` buttons to all four volume rows. Keyboard/controller volume steps are now 5% increments. Changes continue to apply immediately and save through the existing settings/profile path.

### 3. ESC immediately destroyed an active mission

The previous keyboard ESC branch explicitly set the state to `CONTRACT_BOARD`, nulled `self.mission`, and cleared pause state.

Pass 32 replaces that behavior with a real mission pause menu:

1. Resume Contract
2. Settings
3. Abort Contract

Abort requires a second confirmation. ESC/B resumes from the pause menu. Opening Settings from a paused mission returns to the same still-paused mission and keeps the battle/Sovereign music context instead of switching to menu music.

### 4. `windows_dist` could be left empty

The previous Windows batch deleted/recreated `windows_dist` before PyInstaller and the packaged tests had succeeded. A failed build or smoke test could therefore leave the user with an empty final output folder.

Pass 32 now uses a staging build:

`build/pass32_windows_stage` -> packaged tests -> clean-save scan -> portable ZIP -> publish to `windows_dist`

`windows_dist` is replaced only after the staged runtime passes all required gates. A successful build leaves:

```text
windows_dist/
  BUILD_SUCCESS.txt
  HEX_CONTRACT_Windows_x64.zip
  HEXContractRuntime/
    HEXContract.exe
    _internal/...
```

A new root `BUILD_WINDOWS.bat` wrapper is included. Build logs always go to `windows_build_logs/BUILD_LAST.txt`.

The staged runtime is rejected if a `save_profile.json` or crash ZIP leaks into the package, so the release build starts with a clean game save.

## Regression protection

The following gameplay/platform authorities remain byte-identical to Pass 31.1:

- simulation/combat
- all world and layout data
- hero/enemy/civilian data and visuals
- achievements
- save-path implementation/profile schema v9
- crash reporter
- Microsoft runtime/GDK bridge

Pass 29's permanent code audit still passes 36/36 mission first-update combinations and 9/9 battlefield render paths.

## Native boundary

The Linux container still does not provide pygame-ce/Panda3D native runtime packages or a Windows execution environment. The Pass 32 pause/settings behavior is exercised with the existing runtime compatibility harness, audio is measured with FFmpeg EBU R128 analysis, and the Windows batch is contract-checked statically. The final `BUILD_WINDOWS.bat` must still be run on Windows for native packaged acceptance.
