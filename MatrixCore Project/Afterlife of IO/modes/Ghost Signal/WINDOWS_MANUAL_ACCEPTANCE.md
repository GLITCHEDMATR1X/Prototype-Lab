# Windows V1 RC3 Native Acceptance

Run `BUILD_WINDOWS.bat`, then `RUN_WINDOWS_MANUAL_ACCEPTANCE.bat`.

The operator assistant records all final native-only gates:

- bordered window launch and scaling
- F11 fullscreen round-trip
- Alt+Tab focus, rendering, input, and audio recovery
- audible ambience and critical cue sequence
- settings and save persistence after executable relaunch
- full blank-save human playthrough
- migrated-save human playthrough
- clean exit with no crash log

The assistant writes:

```text
release/WINDOWS_MANUAL_ACCEPTANCE.json
```

It cannot report PASS outside native Windows, and its automated contract-test report cannot be used for final promotion.

After it passes, run `PROMOTE_WINDOWS_V1.bat`. Promotion remains blocked unless:

```text
dist/GhostSignalUtopia/WINDOWS_ACCEPTANCE_TEST.txt
  AUTOMATED_GATE=PASS
  FINAL_RESULT=PASS

release/WINDOWS_MANUAL_ACCEPTANCE.json
  report_type=native_windows_manual_acceptance
  sys_platform=win32
  operator_confirmed=true
  final_result=PASS
```
