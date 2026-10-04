AFTERLIFE OF IO — REPLACEABLE SFX

This folder is the replacement point for exploration, battle, and Shrine sound effects.
Keep the semantic stem. The runtime accepts .wav, .ogg, or .mp3 and chooses
the first matching file in this priority: WAV, OGG, MP3.

CUES
 footstep_walk_1   alternating grounded walking step A
 footstep_walk_2   alternating grounded walking step B
 footstep_sprint_1 alternating grounded sprint step A
 footstep_sprint_2 alternating grounded sprint step B
 lantern_resonance Future-learned causal listening pulse
 memory_debris     compatibility stem for one-time drone-remain lore discovery
 shrine_restore    all three First Witness echoes returned
 weather_future    Future exploration weather; overrides shared wind
 weather_past      Past exploration weather; overrides shared wind
 weather_wind      shared exploration fallback; fades around menus/dialogue/battle
 battle_enter    entering an ordinary Entity battle
 lantern_shot    IO fires the lantern
 focus           IO gathers Focus
 guard           IO raises the lantern veil
 boss_hit        a damaging hit removes Guardian Presence / sheds mechanical fragments
 witness_strike  First Witness: Direct Witness response
 gate_anchor     First Witness: The Gate begins its anchor response
 deep_recall     First Witness: Deep Recall response
 counter         IO correctly answers a Guardian tell
 gate_heal       The Gate restores Guardian Presence
 io_hurt         IO loses Resolve
 victory         ordinary Guardian archive opened
 defeat          IO loses a Guardian battle attempt
 flee            IO leaves a battle voluntarily
 shrine_bind     Future Shrine record is bound

The folder may contain placeholders or user-mastered replacements. Pass 54
preserves the current mastered footstep and weather WAVs. Keep one supported
extension per semantic stem so inactive duplicates do not inflate the package.
Missing or unreadable SFX never block gameplay. SFX volume is controlled
separately from music in Settings.

Pass 48 added:
  boss_shatter  final Presence hit / Guardian record breakup

Pass 49 added:
  footstep_walk_1 / footstep_walk_2
  footstep_sprint_1 / footstep_sprint_2
  weather_wind

Pass 50 added:
  weather_future
  weather_past

The Future and Past loops crossfade on era changes. Remove either override to
make that era fall back to weather_wind.

Pass 51 added:
  lantern_resonance

The resonance cue plays once when the Future clue attunes the lantern and on
each valid R pulse. The gameplay cooldown is independent from sound length.

Pass 52 added:
  memory_debris
  shrine_restore

The memory_debris compatibility stem plays once when an unread drone remain is approached. Shrine
restore plays when all three post-binding Witness echoes have been recovered.

Footstep cadence is driven by actual distance travelled. Blocked movement and
airborne hops do not trigger steps. Add mastered replacements using the same
stems; missing cues remain nonfatal.

Machine loop replacement contract:
  machine_loop     powered machine mechanical loop

Pass 129 protects machine_loop on a reserved mixer channel so ordinary one-shot
SFX cannot interrupt it. machine_loop plays continuously while any valid Core/Gear/Pivot drive is powered
in the Beginning/Past exploration world. It stops immediately when no drive is
powered or IO is not in the Past. It is not proximity-gated. Replace
machine_loop.wav with machine_loop.ogg or machine_loop.mp3 if preferred; keep
only one supported extension.
