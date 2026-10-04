ANDREW'S NIGHTMARE — PASS 14 AUDIO

This build now ships with six original procedural ambient WAV loops in:
  assets/audio/music/

and ten original event SFX in:
  assets/audio/sfx/

The files are intentionally WAV because Panda3D's documented native looping path
(setLoop(True)) avoids encoder padding that can create loop gaps.

Ambient playlist:
  01_intercept_hum.wav
  02_empty_carrier.wav
  03_sleep_channel.wav
  04_green_static.wav
  05_false_room.wav
  06_dreamcatcher_core.wav

SFX:
  sleeper_disturb.wav
  stabilizer.wav
  instance_collapse.wav
  null_layer.wav
  null_exit.wav
  gleebs_trace.wav
  memory_seam.wav
  false_sleeper_resolve.wav
  room_recovered.wav
  relay_online.wav

Sleeper-contact datamoshing slows/pitch-wobbles the active loop and fades it out;
the next dream instance advances to another loop. Null Layer stops the score.
Removing any optional audio file must not prevent launch.

Pass 16 adds `sleeper_resonance.wav`, an original DreamCatcher signal-lock cue used only when Andrew successfully reads the real Sleeper from a safe observation distance.
