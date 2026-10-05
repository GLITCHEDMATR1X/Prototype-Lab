HoloVerse drop-in (Pass 282.83 - project audit)

Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked).
No music, no music settings and no cockpit config are included - your own files stay as they are.
You can delete holospace_travel_sequence.py from your HoloVerse folder (dead code, nothing uses it).

The MatrixCore Project fixes (Vector Wars, Utopia Conflict, Mirror's Limbo) are on GitHub in
Prototype-Lab, branch claude/controls-disabled-dimensions-2zb0tq - see the summary in chat.

HoloVerse fixes in this pass:
- The game read your progression save from disk on every single frame (Gleebs' dialogue check).
  It now re-reads it only when it changes - 0 disk reads per frame in the hub, regions and HoloSpace.
- H is now Help everywhere. In the hub, H used to hide the HUD (and saved that), while the help page
  said "Help: H". Hide/show the HUD is now F3. If your HUD is hidden from an old H press, press F3.
- Resizing the window in windowed mode stretched the 3D view and all menus; they now follow the window.
  The HoloSpace corner HUD also re-fits after a resize.
- MatrixCore Gates list showed HoloSpace three times; one entry per destination now.
- The MatrixCore deck showed an internal "_system" folder as a broken mode.
- Removed leftover text: the hub help's "Aircraft: V (after Ember)" line (that aircraft no longer
  exists), "Local guides own each activity", and the developer key list in Settings > World
  (now only shown when developer mode is on with Shift+F9).
- Developer test flags for the removed Ember Hangar / Frost Circuit would crash the game at start.
- README rewritten for the current game (saves, crash logs, controls, music).
