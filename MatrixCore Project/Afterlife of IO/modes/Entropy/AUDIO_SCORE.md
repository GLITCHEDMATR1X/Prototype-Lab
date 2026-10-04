# Entropy State-Aware Score — Pass 28

Entropy now treats music as a gameplay-state layer rather than a playlist.

| State | Track | Runtime rule |
|---|---|---|
| HOME | `score_home_signal.wav` | Stable/unstable HOME exploration |
| SHIP RECOVERY | `score_ship_recovery.wav` | Frozen-timer ship boot tutorial |
| EXPEDITION | `MCF24.mp3` | Normal orbit/surface/interior exploration |
| COLLAPSE | `score_collapse_pressure.wav` | CRITICAL, SUPERNOVA, BLACK HOLE |
| GLEEBS | `score_gleebs_link.wav` | Delivery and completion |
| FAILURE | silence | Prevents pressure music continuing under retry UI |

`MCF24.mp3` is the original user-supplied track and is not rewritten or renumbered.
The four support loops are deterministic 48 kHz stereo WAV files generated from
`music_score.py`; they are intentionally restrained and exist to frame the supplied
track rather than replace it.

## Transition contract

- One streamed music channel only.
- Every active score uses `loops=-1`.
- A state change calls `stop()` before the next `load()` / `play()`.
- Volume is re-applied after every load because SDL_mixer/pygame music loading can reset it.
- Camera/view changes alone never change music.
- Pause/settings preserve the current state instead of restarting it.
- Failure stops music.

## Mix

The score has its own Music slider, multiplied only by Master and the state's authored
base trim. Ship + Effects and World Ambience remain independent categories.

Generated score base trims range from 0.50 to 0.62; normal SFX base levels remain
higher, leaving gameplay-critical ship/effect cues with headroom.
