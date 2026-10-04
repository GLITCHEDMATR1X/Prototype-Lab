ANATOMIC — REPLACEABLE COMBAT AUDIO

Pass 35 uses Panda3D/OpenAL polyphonic voice pools. These existing hologun cues are unchanged audio binaries and remain replaceable:

  left_hologun_fire.wav
  right_hologun_fire.wav
  left_hologun_impact.wav
  right_hologun_impact.wav

Keep the filenames. 16-bit stereo PCM WAV at 48 kHz is the safest replacement format for this build.

These firearm/impact cues no longer share a single Windows PlaySound lane. They use independent Panda3D AudioSound voices and can overlap the new melee arm/sword cues in assets/audio/melee/.
