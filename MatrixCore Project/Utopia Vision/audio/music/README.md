# Replaceable District Soundtracks

Pass 42 gives each Utopia district its own independently replaceable looping soundtrack.

Files:
- `core_unity_forum.wav` — Unity / Forum Nexus
- `north_corporate_terrace.wav` — North / Corporate Terrace
- `east_innovation_pulse.wav` — East / Innovation Pulse
- `south_mirage_promenade.wav` — South / Mirage Promenade
- `west_foundry_works.wav` — West / Foundry Works

## Replace a soundtrack
The simplest workflow is to replace one WAV with another WAV using the exact same filename. No Python edit is required.

You may also edit `district_music.json` and point a track at a different project-relative audio file. Paths outside the project are rejected.

Recommended replacement format: PCM WAV, 16-bit, 22.05 kHz or 44.1 kHz, mono or stereo. OGG may also be used by changing the JSON asset path if the local Panda3D audio backend supports it.

For clean district transitions, make loops that can repeat indefinitely without a loud seam. All supplied placeholder compositions are original, seamless 12-second ambient loops and are intentionally modest in volume so they can be replaced later.

## Runtime behavior
All five district loops are owned by the dedicated Panda3D music manager and remain synchronized while running. Their volumes crossfade according to player position. Unity blends into the four outer districts; neighboring districts crossfade near borders; all district music fades to silence beyond Utopia so natural exterior ambience remains unobstructed. Ocean ambience is a separate layer and is not replaced by this system.
