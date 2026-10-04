# Entropy Ambient Audio System — Pass 3

Entropy uses dedicated loop channels rather than the music stream, allowing ambient sound to follow gameplay state without interrupting one-shot effects or any future soundtrack.

## Channel ownership

| Channel | Owner |
|---|---|
| 0 | Space engine idle / thrust |
| 1 | One-shot ship and weapon SFX |
| 2–3 | Cross-fading planetary and ruin ambience |
| 4 | Ship-interior hum |

Channels 0–4 are reserved so automatic Sound playback cannot steal a persistent loop.

## Runtime rules

- **Space:** engine idle or thrust only; no planetary ambience and no interior hum.
- **Planet surface:** one world-class loop; the ship engine is silenced.
- **Dungeon / castle / catacomb:** the surface loop cross-fades into the matching ruin loop.
- **Ship interior:** all level ambience fades out and only the interior hum remains.
- **Return to a level:** the correct level loop starts again and the hum stops.
- **Return to space:** all level/interior loops stop and the engine loop resumes.
- Repeated synchronization of the same state does not restart or duplicate a loop.

## Authored procedural loops

The deterministic generator creates 16 seamless stereo WAV files at 22,050 Hz:

### Planet surfaces

- `desert` — broad dry wind and low dune resonance
- `ice` — thin polar wind and crystalline shimmer
- `jungle` — humid low drone and organic pulses
- `volcanic` — deep magma rumble and crackling tones
- `crystal` — high resonant glass harmonics
- `oceanic` — slow pressure swell and mist texture
- `fungal` — wet sub-bass bloom and spore pulses
- `rust` — metallic wind and ferric machinery resonance
- `salt` — open airy hiss and sparse mineral tones
- `abyss` — deep basin pressure and distant signals
- `storm` — heavy wind, low thunder texture and pulse
- `roseglass` — glass resonance and pink-noise air

### Ruins

- `dungeon` — enclosed tomb machinery drone
- `castle` — elevated mechanical air and resonant chambers
- `catacomb` — deep hollow pressure and burial pulse

### Ship

- `ship_hum` — steady interior power-core and ventilation hum

## Regeneration

```bash
python tools/generate_ambient_loops.py --force
```

The generator writes `assets/sfx/ambience/manifest.json` and `.ambient_version`. Files are recreated only when missing or when the generator version changes.

## Verification

```bash
python tools/verify_audio_states.py
```

The test uses SDL's dummy audio backend and validates:

- all expected loops load
- stereo PCM format and duration
- seamless endpoint deltas
- no clipping
- engine/ambience/hum exclusivity
- surface and ruin switching
- repeat synchronization without duplicate loops
- interior entry/exit behavior
- return-to-space cleanup

## Pass 17.1 mix controls

The pause-menu Settings page now exposes master, music, ship/effects, ambience, and mute controls. The environment loops use the ambience category; engine and one-shot ship sounds use the ship/effects category; streamed tracks use the music category. All categories are multiplied by master volume and are saved atomically in the per-user settings file.


## Pass 28 streamed score ownership

The persistent ambience channels above remain unchanged. Music uses `pygame.mixer.music`, which is a separate single streamed channel and therefore never competes with reserved ambience/SFX channels.

State routing is authoritative and non-random:

- HOME → `score_home_signal.wav`
- disabled ship recovery → `score_ship_recovery.wav`
- normal expedition → original `MCF24.mp3`
- CRITICAL / SUPERNOVA / BLACK HOLE → `score_collapse_pressure.wav`
- delivery / completion → `score_gleebs_link.wav`
- failure → silence

All score states use infinite looping and stop-before-switch semantics. Panning between SPACE, SURFACE and INTERIOR does not change the score unless campaign or collapse state also changes. The Music volume category remains independent from Ship + Effects and World Ambience.
