HoloVerse drop-in (Pass 282.82)

Copy everything in this zip into your HoloVerse folder (same paths; overwrite when asked).

This zip contains NO music and no music settings: nothing in assets/audio is touched, so your own
tracks and region_music.json stay as they are. (Sorry about the last drop-in overwriting them -
drop-ins will not include music files again.)  It also leaves assets/config/holospace_cockpit.json alone.

If you still have the 8 removed activity folders from Pass 282.81 in Dimensions/, they can be deleted;
the game ignores them either way.

This pass - the warp into HoloSpace:
- No more freeze. Building the 16 dimension planets took several seconds on the frame the warp ended.
  Their textures are now prepared in the background a few seconds after the game starts and kept in
  your cache folder (%LOCALAPPDATA%\GLITCHED MATRIX\HoloVerse\cache\planets), so the switch takes a
  fraction of a second. The planets look exactly the same as before.
- New warp: the view darkens into deep space with soft star streaks (0.45 s), the switch happens behind
  full cover, then the streaks slow and fade out over the live cockpit view (1.5 s). HoloSpace is already
  running while it fades - you can fly straight away.
- No blinding flash: no bright core, the streaks are capped well below white.
- The frozen world is never shown behind the warp any more.
