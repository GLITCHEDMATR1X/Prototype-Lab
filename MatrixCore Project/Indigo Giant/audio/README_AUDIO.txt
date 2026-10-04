THE INDIGO GIANT — SOUND & MUSIC FILES (Pass 40)
================================================

Every sound in the game is a plain file in this folder. Replace any of them with
your own. Keep the name; the format can be .wav, .ogg, .flac or .mp3. If a file is
missing, that sound is simply silent. The game never errors over audio.

VARIANTS
  An event can have several files: footstep_giant_01.wav, footstep_giant_02.ogg, ...
  (or just footstep_giant.wav). The game picks one at random each time and never
  repeats the same file twice in a row. Add or remove variants freely.

3D SOUND (important)
  Sound effects are placed in the world and heard from the camera. They get quieter
  with distance and pan left/right. OpenAL can only do this with MONO files. A stereo
  file still plays, but at full volume with no direction. Export effects as mono.
  Music and the ambience beds can be stereo.

SFX  (audio/sfx/)
  footstep_human      each human step (louder when jogging/sprinting, quieter crouched)
  footstep_giant      each Nyx step, heard far away
  footstep_red        each Crimson step, heard from very far: you hear it coming
  land_human / land_giant       jump landings
  kneel_giant / stand_giant     Nyx kneeling down / standing back up
  stomp_red           Crimson's stomp attack hitting the ground
  roar_red_hunt       Crimson starts hunting you (at most every 25 s)
  roar_red_scared     Crimson is scared off at low health
  roar_red_ko         Crimson knocked out
  roar_red_return     Crimson coming back after lurking (plays distant and washed out)
  roar_red_heave      Crimson's grunts while heaving at your shell
  call_indigo         Nyx answering your whistle / moving to defend you
  hum_indigo_sense    Nyx sensing a find
  gesture_come / gesture_stay / gesture_shade / gesture_lift / gesture_goto
  whistle             the whistle (Q)
  punch_swing / punch_hit       giant fists
  branch_smash        a blood branch breaking
  dig / eat / patch
  shell_enter / shell_exit / shell_creak (while Crimson heaves) / shell_flip
  shell_lift / shell_place      Nyx picking up / setting down a shell
  landmark_study      studying a landmark
  human_hurt / human_down
  lore_read           an etching lighting up as you read it (Pass 61)
  gleebs_arrive       the sky opening and Gleebs' beam coming down (heard everywhere)
  gleebs_voice        Gleebs speaking (a few soft syllables under each line)
  gleebs_depart       Nyx and Orbit rising up the beam, leaving REDACTED
  heartbeat           loop: plays when overheating (heat 85+) or badly hurt (25 hp or less)
  amb_wind            loop: desert wind (louder riding, quiet inside a shell)
  amb_heat            loop: heat shimmer, rises with heat

MUSIC  (audio/music/)
  ambient_NN          ambient cues. One plays at a time, then a quiet gap of 18-45 s,
                      then the next (shuffled). Add as many as you like.
  battle_NN           battle loop (the first one found). It fades in over 2.5 s when the
                      Crimson is hunting within 130 m or Nyx is fighting, holds 8 s
                      after it ends, then fades out over 6 s. Ambient ducks under it.
  stinger_landmark    one-shot when you study a landmark
  stinger_red_return  one-shot when Crimson comes back
  stinger_ko          one-shot when Crimson is knocked out
  Make battle loops loop cleanly (the end should flow into the start).

TUNING (optional JSON files in this folder)
  audio_settings.json   master / music / sfx / ambience volumes (0..1)
  audio_manifest.json   per event:
                          min     metres at which it is full volume
                          max     metres beyond which it is silent (not played at all)
                          volume  0..1
                          pitch   random play-rate variation, e.g. 0.06 = +/-6 %
                          voices  how many copies can overlap
  Delete either file to go back to the built-in defaults.

IN GAME
  M   mute / unmute the music

PLACEHOLDERS
  The files shipped here were synthesised by tools_make_placeholder_audio.py (no
  third-party content). Running it again only fills in missing files. It never
  overwrites yours unless you pass --force.
