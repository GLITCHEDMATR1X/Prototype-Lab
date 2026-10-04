# Etch-Line SFX Custom Folder

Put replacement sounds here when you want them to stay with this Prototype Lab mode.

Priority: `overrides` wins first, then this `custom` folder, then shared/generated fallback sounds.

Supported formats: `.wav`, `.ogg`, `.mp3`.

Use the official filename when possible:

| Effect key | Best filename | What it replaces |
|---|---|---|
| `fire` | `mech_fire.wav` | Core Lance / normal weapon fire |
| `hit` | `core_hit.wav` | Weak-core hit confirmation |
| `armor` | `armor_hit.wav` | Body/armor hit sparks |
| `break` | `shield_break.wav` | Shield-break burst |
| `tell` | `enemy_tell.wav` | Enemy attack warning/tell |
| `chain` | `chain_arc.wav` | Chain arc / lightning jump |
| `recharge` | `recharge.wav` | Recharge/energy feedback |
| `kill` | `mech_kill.wav` | Enemy core rupture / kill boom |
| `imploder` | `imploder_pulse.wav` | Imploder shot/crush |
| `magnet` | `magnet_field.wav` | Proximity Magnet pulse/field |
| `disassemble` | `disassembler_cut.wav` | Disassembler cut/part detach |
| `pickup` | `weapon_pickup.wav` | Ammo cache / pickup / unlock |
| `dry` | `dry_click.wav` | Empty ammo / unavailable click |

Short aliases also work, like `fire.wav`, `hit.wav`, `magnet.wav`, or `dry.wav`, but the official filenames are clearer.
