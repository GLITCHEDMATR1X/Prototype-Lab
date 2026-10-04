# The Indigo Giant — Animation Map

Source: `Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb`

## Current gameplay clips
- `Idle_Loop` — 2.5000 s — used
- `Walk_Loop` — 1.3333 s — default WASD
- `Jog_Fwd_Loop` — 0.9333 s — SHIFT + WASD
- `Sprint_Loop` — 0.6667 s — CTRL + SHIFT + WASD

## Strong next-control candidates
### Locomotion still to map
- `Jump_Start` — 1.3333 s
- `Jump_Loop` — 2.5000 s
- `Jump_Land` — 1.2667 s
- `Crouch_Idle_Loop` — 2.9333 s
- `Crouch_Fwd_Loop` — 2.0000 s

### Interaction / reach
- `Interact` — 2.0000 s
- `Fixing_Kneeling` — 5.2000 s

`Fixing_Kneeling` gets the body low enough to be useful for a giant reaching toward tiny humans, but its hand motion is task-specific. It is a good prototype kneel candidate, not a final bespoke social interaction.

### Sitting sequence
- `Sitting_Enter` — 1.3000 s
- `Sitting_Idle_Loop` — 1.6667 s
- `Sitting_Exit` — 1.0333 s

This is a complete transition set, but it will need a seat/ground anchor and position correction before it becomes gameplay-safe.

## Clips that should NOT be forced into shoulder-carry gameplay
- `PickUp_Table` — 0.8333 s

The pose is designed around a table/waist-height pickup and is not a convincing ground-level tiny-human lift.

## Other usable library clips
- `A_TPose`
- `Dance_Loop`
- `Death01`
- `Driving_Loop`
- `Hit_Chest`
- `Hit_Head`
- `Idle_Talking_Loop`
- `Idle_Torch_Loop`
- `Pistol_Aim_Down`
- `Pistol_Aim_Neutral`
- `Pistol_Aim_Up`
- `Pistol_Idle_Loop`
- `Pistol_Reload`
- `Pistol_Shoot`
- `Punch_Cross`
- `Punch_Jab`
- `Push_Loop`
- `Roll`
- `Sitting_Talking_Loop`
- `Spell_Simple_Enter`
- `Spell_Simple_Exit`
- `Spell_Simple_Idle_Loop`
- `Spell_Simple_Shoot`
- `Swim_Fwd_Loop`
- `Swim_Idle_Loop`
- `Sword_Attack`
- `Sword_Idle`
- `Walk_Formal_Loop`

## Audit result
- Total embedded animations: 43
- Load/skin validation: 43 / 43 pass
- All tested start/mid/end poses: finite
- Root translation range across all 43 clips in this non-root-motion GLB: 0 on X/Y/Z

That means gameplay code must continue to own world movement; animations are visual pose/gait data.

## Model work still needed later
The current rig itself does not need replacement for basic movement. The missing pieces are interaction-specific:
- shoulder attachment anchor for the human
- hand/palm carry anchor
- dedicated giant ground-level reach/lift animation
- dedicated place-on-shoulder / remove-from-shoulder animation
- optional dedicated neutral kneel rather than reusing `Fixing_Kneeling`

## Control work still needed later
A sensible remaining order is:
1. jump state chain
2. crouch/crouch-walk
3. generic interact
4. kneel/sit state transitions
5. bespoke carry/shoulder interaction

Do not bind all of these at once.

## Pass 22 locomotion feel
The Indigo Giant still uses the same `Walk_Loop`, `Jog_Fwd_Loop`, and `Sprint_Loop` clips, but interactive movement now has slower cadence/top speed plus acceleration, braking, and turn inertia. Human gait behavior is unchanged.

## Pass 23 implemented
- `Jump_Start` -> one-shot takeoff phase
- `Jump_Loop` -> airborne phase
- `Jump_Land` -> one-shot landing phase
- Control: `SPACE`
- Human and giant share the same state chain, with slower takeoff/landing timing and lower relative jump height for the giant.

## Pass 24 mapped
- `Crouch_Idle_Loop` — hold C while stationary
- `Crouch_Fwd_Loop` — hold C while moving
- Crouch overrides jog/sprint and blocks jump while held.

## Pass 25 mapped — giant kneel
- `Fixing_Kneeling` is now used as a giant-only prototype kneel source.
- Control: `K` toggles kneel / stand while controlling the Indigo Giant.
- Entry uses the clip's first ~1.2 s, where the body reaches the low posture.
- Held kneel uses a stable sample around 2.4 s instead of looping the clip's task-specific hand motion.
- Exit reverses the same entry range back to standing.
- Movement, jump, and control switching are blocked while the giant is kneeling / transitioning.
- Smoke measurement: right hand height above local terrain drops from ~7.91 world units standing to ~2.43 kneeling (~69% lower).

This is still a prototype interaction posture. A bespoke neutral kneel / hand-off animation remains desirable before final shoulder-carry presentation.

## Pass 26 — Red Giant NPC mapping
The hostile Red Giant reuses the same humanoid rig and giant-scale locomotion model but is autonomous only.

Current NPC clips loaded:
- `Idle_Loop` — no target/outside awareness
- `Walk_Loop` — close pursuit
- `Sprint_Loop` — distance pursuit
- `Jump_Land` — prototype stomp attempt

Additional player/Indigo clips are intentionally not pre-baked for the Red Giant until a behavior actually requires them.

## Pass 27 — giant melee mapping

| Purpose | Clip | Status |
|---|---|---|
| Light punch | `Punch_Jab` | MAPPED |
| Heavy/alternate punch | `Punch_Cross` | MAPPED |
| Basic hit reaction | `Hit_Chest` | MAPPED |
| Giant defeat pose | `Death01` | MAPPED |

Combat uses one timed hit window per punch and a 5.4-unit giant melee range. The Red Giant uses the same combat clip family as the Indigo Giant but remains AI-only.
