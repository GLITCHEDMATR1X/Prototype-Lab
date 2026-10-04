# Etch-Line Audio Replacement Guide — Pass15

## SFX replacement rule

Use **WAV only** for effect replacements.

Drop replacement files in:

```text
assets/audio/sfx/overrides/
```

This folder wins first. The `customfx` folder is now a reference folder containing WAV printouts of the current generated effects. Copy from there, edit externally, then put the final WAV in `overrides`.

## Current replacement names

| Effect | Put this WAV in overrides |
|---|---|
| Core Lance fire | `mech_fire.wav` |
| Core hit | `core_hit.wav` |
| Armor hit | `armor_hit.wav` |
| Shield break | `shield_break.wav` |
| Enemy tell/warning | `enemy_tell.wav` |
| Chain arc | `chain_arc.wav` |
| Recharge | `recharge.wav` |
| Enemy kill/rupture | `mech_kill.wav` |
| Imploder | `imploder_pulse.wav` |
| Proximity Magnet | `magnet_field.wav` |
| Disassembler | `disassembler_cut.wav` |
| Ammo/pickup | `weapon_pickup.wav` |
| Empty ammo click | `dry_click.wav` |

## Folder meanings

```text
assets/audio/sfx/customfx/   reference printouts of the current SFX
assets/audio/sfx/overrides/  your replacement WAV files; highest priority
assets/audio/sfx/custom/     legacy folder kept for old builds
assets/generated/sfx/        generated fallback owned by the build
```

## Music / ambience loops

Drop WAV loops here:

```text
assets/audio/loops/
```

Any WAV filename is accepted. The game scans the folder automatically on launch and starts the first sorted WAV it finds.

## Depth / stereo behavior

Combat impact sounds, enemy warnings, kills, chain arcs, pickups, imploder pulses, and magnet fields can now be played from their world position. Stereo WAV files keep their stereo image, and positional SFX are attached to temporary world nodes when OpenAL/3D audio is available.

Run this anytime to print the live map:

```bash
python -B main.py --sfx-map
```


## Pass16 Audio Palette + Weapon/Wave Expansion
- Expanded the WAV-only SFX map to the uploaded palette: burst, automatic, heavy armor, deflect, metal break, enemy voices, explosions, objective complete, ricochet, and special pickup.
- Added weapon slots 5 and 6: Burst Splitter and Auto Lattice.
- Capture-zone enemies now wait until the player steps into the active node ring, then spawn from behind building silhouettes and approach the player.
- Existing overrides folder remains the final replacement folder: `assets/audio/sfx/overrides/`.
