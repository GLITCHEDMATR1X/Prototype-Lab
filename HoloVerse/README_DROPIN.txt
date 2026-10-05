HoloVerse drop-in (Pass 282.81)

1) DELETE these folders from your HoloVerse folder (a zip cannot delete them for you):
     Dimensions/Ember Hangar          Dimensions/Forest Growth
     Dimensions/Frost Circuit         Dimensions/Hills of Life
     Dimensions/HoloForge             Dimensions/Metropolis Robot Lab
     Dimensions/Oddities              Dimensions/Urban Warzone
   Optional: assets/audio/regions/holoforge.mp3, regions/flat/holoforge, regions/mushroom/oddities,
   regions/metropolis/robot_lab, libraries/oddities_blueprint_library.json
   (The game ignores all of these even if you leave them, but they are dead weight.)
   Keep Dimensions/HoloSpace Region - that is the route into HoloSpace.

2) Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked).
   assets/audio/regions/*.mp3 are the music placeholders: if you already put your own tracks in,
   skip those files.

This pass - removed the in-world region activities:
- Gone: Frost Circuit, Ember Hangar, Forest Growth (planter), Hills of Life, Oddities, Urban Warzone,
  Metropolis Robot Lab, and HoloForge (including its station at the hub; the 8 region artifacts stay).
- The region guides now open their dimension gate directly when you press ENTER:
    Vanta -> Glyphbound, Solace -> Anomaly Sequence, Ember -> Vector Wars,
    Archivist -> The Archivist, Sable -> Anatomic   (IO, Nyx, Mirror and Orbit unchanged)
  The second "activity" button in their dialogue is gone.
- Campaign: the five activity goals became "enter <guide>'s gate" goals (still 9 signals).
- The regions themselves (scenery, music, bots, HoloSpace) are unchanged.
