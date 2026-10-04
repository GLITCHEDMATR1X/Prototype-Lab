HoloVerse drop-in (Pass 282.80)

Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked):
  main.py, holoverse_mode_runtime.py, holoverse_child_bootstrap.py,
  holoverse/deep_space.py, holoverse/deep_space_combat.py, holoverse/deep_space_holohud.py,
  holoverse/holospace_cockpit_config.py, holoverse/dimension_planets.py, holoverse/fungal_visuals.py,
  holoverse/dimensions/registry.py,
  assets/audio/region_music.json, assets/audio/audio_library_manifest.json, assets/audio/holoverse_music_cues.json,
  assets/audio/regions/  (holoverse.mp3 = the HoloVerse song, moved here; the rest are silent placeholders -
                          once you have put your own tracks in, do NOT copy the placeholders over them again),
  assets/config/holospace_cockpit.json   (keep your own copy if you already edited it),
  assets/config/holoverse_audio_bus.json, config/holoverse_settings.json, World Shell/audio_profile.json,
  ui/ui_manifest.json, matrixcore/gleebs_dialogue.json
Your old assets/audio/Holoverse.mp3 can be deleted (it is only used if regions/holoverse.mp3 is missing).

For the Prototype-Lab build, MatrixCore Project/HoloCore/main.py is updated on GitHub (standalone HoloCore
plays regions/holocore.mp3 too).

This pass:
Music
- The HoloVerse song now lives with the others: assets/audio/regions/holoverse.mp3.
- It plays on the title screen, at the hub and across the FLAT region. It was silent on the title
  screen (it played the silent placeholder of whatever region your save last remembered).
- Regions now follow the ring you are standing in. Desert used to get the Urban track, and Ice got HoloSpace's.
- HoloCore has its own track: assets/audio/regions/holocore.mp3 (placeholder - replace with your MP3).
  HoloVerse plays it while HoloCore is open; other dimensions keep their own soundtracks.
Crashes
- Could not reproduce a crash entering Green Hills or any other region (artifacts, region travel, walking
  across every border, Oddities/Forest Growth with saved items, live audio) - no errors anywhere.
- Hardened the log writer: on Windows a printed status line with a character the console can't show
  could raise inside game code. Prints can no longer crash the game.
- New: native_crash.log. If the game closes without an error, send me these two files:
    %LOCALAPPDATA%\GLITCHED MATRIX\HoloVerse\logs\native_crash.log
    %LOCALAPPDATA%\GLITCHED MATRIX\HoloVerse\logs\latest.log   (and crash.log if there is one)
