HoloVerse drop-in (Pass 282.76)

Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked):
  main.py
  holoverse_child_bootstrap.py
  holoverse/deep_space.py
  holoverse/deep_space_combat.py          (new)
  holoverse/deep_space_holohud.py         (new)
  holoverse/holospace_cockpit_config.py   (new)
  holoverse/dimension_planets.py
  holoverse/fungal_visuals.py
  holoverse/dimensions/registry.py
  assets/config/holospace_cockpit.json    (new - the editable ship interior)
No dimension project needs an edit.

HoloSpace - this pass:
- Defence wings: every dimension planet and Dyson Prime has a defence perimeter. Fly far enough toward one
  (planets: 400 km of travel toward it, Dyson Prime: closer than 30 AU) and you get a warning, then you are
  pulled out of supercruise and a wing launches (3 interceptors, 5 at Dyson Prime). Red brackets mark them.
  Turn back far enough and they break off; each takes 3 laser hits.
- Shield and hull: hits drain the shield first, then the hull. Every hit on an asteroid recharges 5% shield
  (bigger rocks take several hits). Hard collisions damage you too.
- Lose the hull and the ship is destroyed: you respawn at the MatrixCore hub; re-entering HoloSpace gives a fresh ship.
- Holographic HUD: shield/hull/boost, speed/throttle/mode and the message/threat strip are holo panels inside
  the cockpit, in the cockpit theme's colours. The flat screen keeps only the reticle.
- Editable interior: assets/config/holospace_cockpit.json sets the colour themes (hull, glass, trim, HUD) and the
  window design (number of sides, size, frame/strut thickness, glass tint, struts on/off). Restart to apply.
  The theme you pick with C in flight is remembered in your save folder.

Earlier passes (still included): octagonal canopy, left-click lasers, held Shift boost, farther fading asteroid
fields, no survey rings, all 17 planets, Mushroom sky ring fix; dimension controls/display fixes; planet unlocks
for Gleebs' archive; hub artifact activation.
