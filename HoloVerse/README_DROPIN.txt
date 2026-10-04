HoloVerse drop-in (Pass 282.79)

Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked):
  main.py, holoverse_mode_runtime.py, holoverse_child_bootstrap.py,
  holoverse/deep_space.py, holoverse/deep_space_combat.py, holoverse/deep_space_holohud.py,
  holoverse/holospace_cockpit_config.py, holoverse/dimension_planets.py, holoverse/fungal_visuals.py,
  holoverse/dimensions/registry.py,
  assets/audio/region_music.json, assets/audio/audio_library_manifest.json,
  assets/audio/regions/*.mp3 + README.txt   (placeholders - once you have put your own tracks in,
                                             do NOT copy these over them again),
  assets/config/holospace_cockpit.json   (keep your own copy if you already edited it),
  ui/ui_manifest.json, matrixcore/gleebs_dialogue.json

This pass - region music:
- Every HoloVerse area loops its own soundtrack, one song at a time:
    FLAT region (MatrixCore hub ring)  -> assets/audio/Holoverse.mp3 (unchanged, your song)
    Forests       -> assets/audio/regions/forests.mp3
    Green Hills   -> assets/audio/regions/green_hills.mp3
    Mushroom      -> assets/audio/regions/mushroom.mp3
    Desert        -> assets/audio/regions/desert.mp3
    Ice           -> assets/audio/regions/ice.mp3
    Urban         -> assets/audio/regions/urban.mp3
    Metropolis    -> assets/audio/regions/metropolis.mp3
    HoloSpace     -> assets/audio/regions/holospace.mp3
    HoloForge     -> assets/audio/regions/holoforge.mp3
- The region files are 4-second silent MP3 placeholders. Drop your MCF tracks in with the same names
  (MP3 works; OGG/WAV too - change the name in region_music.json). Per-track volume is in that file too.
- Holoverse.mp3 plays the whole song on loop again (it used to be chopped into short slices for every area).
- No other area borrows Holoverse.mp3: a missing region file means that area is silent.
- Dimensions keep their own soundtracks: HoloCore, the Indigo Giant, etc. get no HoloVerse music on top.
  Fixed: the shared dimension runtime handed Holoverse.mp3 to dimensions as their music (Vector Wars
  played it ahead of its own tracks).

Still included: HoloSpace nav lock / throttle presets / hit marker, loading card, pause screen buttons,
archive unlock count, Zonez removed, real pause in dimensions, corner holo HUD, defence wings, hub respawn,
editable cockpit, lasers, boost, asteroid fields, planets and archive unlocks, dimension controls/display
fixes, hub artifacts.
