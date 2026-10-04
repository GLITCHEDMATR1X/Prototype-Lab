# Operation StarFall Progress / Result Standard v0.1

Pass42 starts the progress/result mastering lane. Every active world must return the same result shape so the StarFall shell and Prototype Lab can trust world completion data without per-world exceptions.

## Active worlds covered

- Mimas Snowfield (`mimas_snowfield`)
- Enceladus Ice (`enceladus_ice`)
- Iapetus Ridge (`iapetus_ridge`)
- Titan Methane Coast (`titan_methane_coast`)

## Required result fields

Every moon result packet must include:

```text
version
world_key
level_id
level_name
objective_name
progress_percent
completed
score
lab_points_awarded
time_seconds
failures
badges
stats
return_to_lab
generated_at
```

## Rules

1. `world_key` must be one of `mimas`, `enceladus`, `iapetus`, or `titan`.
2. `level_id` must match the active world registry.
3. Completed runs must report `progress_percent = 100`.
4. Completed runs must include `level_complete` in badges.
5. `return_to_lab` must be true for completed world runs.
6. Lab points are awarded by the result packet, not by loose UI text.
7. The StarFall shell may record the result summary, but Prototype Lab remains the authority for saving shared points.
8. Failed or partial returns may report less than 100 percent, but must still validate and keep non-negative score/points.

## Output paths

Active world result outputs:

```text
Worlds/verification/reports/level_result.json
Worlds/verification/reports/level_result.md
Worlds/verification/reports/lab_profile_preview.json
```

All-world validation output:

```text
Worlds/verification/reports/all_world_progress_contract.json
Worlds/verification/reports/all_world_lab_profile_preview.json
```

StarFall shell embedded-return validation output:

```text
verification/reports/operation_result_contract_self_test.json
```

## Acceptance gate

Pass42 is accepted only if all active worlds validate through `--all-world-progress-contract-test`, individual `--level-contract-test`, individual `--level-result-test`, and the StarFall shell receives a standardized embedded-return result packet.
