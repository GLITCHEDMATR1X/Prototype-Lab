HoloVerse drop-in (Pass 282.84)

1) DELETE the folder  MatrixCore Project\HoloUtopia  (HoloUtopia is removed from the game).
2) Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked).
   No music, music settings or cockpit config are included.

Fixes:
- ESC now works in every dimension HoloVerse hosts (Glyphbound, Anatomic and Fractured Nemesis had no
  usable ESC). ESC opens the HoloVerse pause card: RESUME, RETURN TO MATRIXCORE, and DIMENSION MENU for
  dimensions that have a menu of their own (HoloShell, Lens Tour, Utopia Conflict, Mirror's Limbo, Indigo
  Giant). ESC again resumes. TAB still returns home. The Archivist keeps its own ESC (closes its panels
  first, then pauses).
- Entering and leaving dimensions now fades from black instead of popping (the return fade existed but a
  dimension's cleanup detached it, so it never showed).
- Strafing while holding Shift: keys pressed while Shift/Ctrl/Alt was held were ignored (Panda sends
  "shift-a" instead of "a"). Fixed on foot and inside dimensions. In HoloSpace, side thrusters are stronger
  while boosting.
- HoloUtopia removed. Its planet design (the crystal world with the ring) now belongs to The Archivist,
  which was one of four look-alike crystal planets - it is the exact same design.
- The game re-added Gleebs lines about the removed activities to matrixcore/gleebs_dialogue.json at start.
