# HoloCore source recovery authority

The only supplied HoloCore source authority is `MatrixCore Project.rar`.
That archive is never modified by this pass.

Source archive SHA-256:
`d80418142ef3c0cfbc1244cbb537e02bb24edc7f01edddde587cd3d74ec4aee1`

The external-dimension conversion deliberately leaves the large standalone
`main.py` byte-for-byte identical to the RAR copy. HoloVerse integration is
owned by the small folder-local responder / native-adapter layer.

Expected installation:

```text
Prototype Lab/
  HoloVerse/
  MatrixCore Project/
    HoloCore/
```

Normal players launch HoloVerse first. Standalone HoloCore development may
still launch `main.py` directly.

## Pass HC-1 (upward strata, open column, vessel)

`main.py` is still byte-for-byte the RAR copy (MD5 `92abebe758ced916967138c93b307f8d`), and so are the creature files `holo_jellyfish.py`, `holo_mermaid.py` and `holo_octopus.py`.

HC-1 changes only these modules:
- `dimensions/outer_flat_world.py`: builds and updates `dimensions/holocore_strata.py`.
- `holo_vessel.py`: Shift boost, a hull height band, and floating out at altitude.
- `holoverse_native_adapter.py`: rise and sink on foot, the boost, help text, and cleanup when you leave.

New files: `holocore_line_kit.py`, `dimensions/holocore_strata.py`, `assets/strata/`, `tools/validate_holocore_hc1.py`, `tools/smoke_holocore_strata.py`.
