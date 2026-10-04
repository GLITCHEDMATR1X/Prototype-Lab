AFTERLIFE OF IO — REPLACEABLE VARIANT CONTRACT

All files in this tree are optional presentation. Missing, unreadable, or
wrong-sized files fall back to the accepted game art and never block startup.

WORLD BACK LAYERS — exact size 3930x1130 PNG
 world/future/witness_defeated.png
 world/future/witness_recorded.png
 world/future/witness_restored.png  (optional Pass 52 Shrine reconstruction)
 world/past/witness_defeated.png

Each file fully replaces only the deepest numbered layer in its world. Every
nearer numbered layer, actor depth band, walk mask, and camera crop stays
unchanged. Preserve the original alpha canvas and registration when replacing.
If witness_restored.png is absent after all three Witness echoes are recovered,
the runtime keeps witness_recorded.png rather than falling back to base art.

BATTLE BACKGROUNDS — recommended size 1280x720 PNG
 battle/boss1.png through battle/boss6.png
 battle/finalboss.png

The active Entity chooses the matching semantic filename. The First Witness is
boss1. If a slot is absent, assets/current/battle/background.png is used; if
that is also absent, the procedural chamber is used.

Pass 54 verifies all seven semantic slots at 1280x720 and losslessly
recompresses their PNG containers without changing decoded pixels or authored
metadata.

WEATHER PRESENTATION

Particle weather uses every PNG in:
 assets/source/particles/

The two era folders also contain one optional transparent alpha sheet:
 weather/future/overlay.png
 weather/past/overlay.png

Each overlay is tiled in both axes with alternating mirrored neighbors and drifts slowly like wind. Hard image edges are
hidden because matching edge pixels meet at each repeated boundary. Any positive PNG size works.
This layer renders behind the active walk layer and therefore behind IO,
foreground scenery, and UI. Replace the PNGs freely; missing/corrupt files are
ignored.

TRANSITION OVERLAYS — recommended size 1280x720 transparent PNG
 transitions/time_shift.png
 transitions/battle_entry.png
 transitions/shrine_bind.png

Other positive image sizes are scaled to the logical screen. Keep broad soft
alpha around the edges; overlays never affect input, timing, or saved state.

WORLD WEATHER AUDIO — assets/audio/sfx
 weather_future.wav / .ogg / .mp3
 weather_past.wav / .ogg / .mp3
 weather_wind.wav / .ogg / .mp3  (shared fallback)

Keep one supported extension per semantic stem. World-specific loops crossfade
when Tab changes the active era and fade around pause, dialogue, and battle.
