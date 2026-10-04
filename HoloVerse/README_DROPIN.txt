HoloVerse drop-in (Pass 282.77)

Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked):
  main.py
  holoverse_child_bootstrap.py
  holoverse/deep_space.py
  holoverse/deep_space_combat.py
  holoverse/deep_space_holohud.py
  holoverse/holospace_cockpit_config.py
  holoverse/dimension_planets.py
  holoverse/fungal_visuals.py
  holoverse/dimensions/registry.py
  assets/config/holospace_cockpit.json   (keep your own copy if you already edited it)
  ui/ui_manifest.json
  matrixcore/gleebs_dialogue.json

This pass:
- Zonez removed: no artifact style, no Gleebs lines, no UI manifest entries; and if an old save still links
  to it, Gleebs' archive and HoloSpace simply ignore it (no "signal lost" entry, no planet).
  Delete the "MatrixCore Project/Zonez" folder too (the Prototype-Lab branch already does).
- Pause inside dimensions: ESC now really pauses dimensions that had no pause of their own (HoloCore, Vector
  Arena, HoloTactics, HoloUtopia, Utopia Conflict, and The Archivist once nothing is open): the dimension
  freezes, the camera stops, the cursor is free; ESC resumes, TAB returns to MatrixCore. Dimensions with their
  own pause menu (Mirror's Limbo, HoloShell, Glyphbound, Anatomic, Utopia Lens Tour, Indigo Giant) keep it.
  The Archivist part needs its own small change: "MatrixCore Project/The Archivist Dimension/archive3d/mode.py"
  (on the Prototype-Lab branch).
- HoloSpace cockpit HUD: four compact holo panels in the canopy corners, outside the window - SHIP (shield,
  hull) bottom-left, FLIGHT (speed, throttle, mode) bottom-right, SYSTEMS (boost, Dyson Prime) top-left,
  COMMS (messages, threats) top-right. They follow the screen's field of view and aspect ratio.

Still included from earlier passes: defence wings, shields/hull and hub respawn, editable cockpit, lasers,
boost, asteroid fields, planets and archive unlocks, dimension controls/display fixes, hub artifacts.
