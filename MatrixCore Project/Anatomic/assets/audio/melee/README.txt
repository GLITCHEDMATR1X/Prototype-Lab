ANATOMIC — REPLACEABLE MELEE AUDIO

Pass 35 adds independent Panda3D/OpenAL voice pools for arm motion, sword motion, impacts, and firearm cues.

Replace these files while keeping their filenames and using 16-bit PCM WAV for the most predictable runtime behavior:
  left_arm_move.wav     — left holographic arm movement / swing
  right_arm_move.wav    — right holographic arm movement / swing
  sword_move.wav        — laser sword movement / whoosh
  sword_hum_loop.wav    — low continuous laser sword idle hum while melee mode is active

The included files are restrained procedural placeholders. Arm and sword movement are separate cues on purpose: a right-arm swing can play the arm swish and sword whoosh simultaneously. Impacts use separate pools as well.

The game no longer uses Win32 winsound as a fallback because that backend has one asynchronous PlaySound lane and causes newer cues to replace older ones. The supported gameplay backend is Panda3D OpenAL. If OpenAL cannot initialize, the game continues without audio rather than silently reverting to non-polyphonic behavior.
