# Vector Wars Pass 15 — Phase Music Authority

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING (pygame-ce runtime unavailable in this container)
TARGET-RUNTIME TEST: NOT RUN

## Single task
Add a replaceable campaign soundtrack authority with at least nine tracks: three each for Ground, Air, and Ocean, while preserving the existing audio/HoloVerse contracts.

## Implemented
- Added `music_library.py` and `assets/music/music_manifest.json` as the phase-music authority.
- Added nine original procedural placeholder WAV loops: 3 Ground, 3 Air, 3 Ocean.
- Phase music switches automatically through the existing combat-mode authority, including F4/TAB developer front testing.
- Player-owned `custom_audio/music/ground`, `/air`, and `/ocean` pools can replace the shipped pool per phase without modifying game code.
- Existing ambient/HoloVerse profile music remains fallback-only.
- Preserved `HOLOVERSE_ROOT_OWNS_MUSIC` behavior so a HoloVerse host can suppress local Vector Wars music.
- Added independent SFX controls: comma/period.
- Added independent music controls: left/right bracket.
- Existing minus/plus remains master audio; M remains mute.

## Regression fixes discovered during this pass
1. pygame-ce resets music volume when a new music file is loaded. The prior Vector Wars code set volume before `load()`. Pass 15 now loads first, then reapplies effective music gain, then starts playback.
2. The old rotation deadline used `time.time()` while the rotation check compared against game `t_now`, so automatic track rotation could fail indefinitely. Pass 15 puts both rotation deadline and check on `time.monotonic()`.
3. Runtime audio self-test now fails if any campaign phase resolves fewer than three music tracks.

## Placeholder track specification
All nine bundled placeholders are original procedural test loops intended for replacement later:
- 12.0 seconds each
- mono PCM WAV
- 22,050 Hz
- 16-bit
- low-level electronic beds designed not to overpower gameplay-critical SFX

See `verification/Pass15_MusicTrack_Audit.json` for hashes and signal checks.

## Reference basis
- pygame-ce `pygame.mixer.music`: music load/playback/volume behavior, including volume reset after loading a new track.
- Microsoft Xbox Accessibility Guideline 105: independently adjustable music and active sound effects.

## Validation
- Pre-change Pass 14 regression gate: 17/17 PASS.
- Pass 15 expanded regression gate: 19/19 PASS.
- 9/9 WAV files parse with Python's WAV reader.
- 9/9 tracks are non-silent and byte-distinct.
- 3/3 tracks resolve for each Ground/Air/Ocean phase.
- Player phase override precedence: PASS.
- HoloVerse root-music ownership contract preserved: PASS.
- Normal gameplay HUD layout unchanged; Field Guide audio copy only.

## Verification boundary
pygame-ce 2.5.7 is still unavailable to execute in this container, so actual mixer playback, audible transitions, and runtime volume behavior remain target-runtime acceptance gates. This pass does not claim auditory acceptance from static tests.
