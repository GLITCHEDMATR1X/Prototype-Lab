# Chapter One V1 RC3 Release Checklist

## Passed in source and packaged-runtime environment

- [x] Frozen schema-6 profile migration matrix
- [x] Corrupt-save recovery and future-save write protection
- [x] Complete campaign regression
- [x] Blank-save executable acceptance through all 11 buildings
- [x] Migrated-save executable acceptance from schema 5
- [x] F1/F2/pause/fullscreen/focus input acceptance
- [x] Native Windows manual-assistant contract
- [x] Final-promotion rejection and acceptance contract
- [x] 1080p and 720p visual verification
- [x] PyInstaller onedir packaged-runtime acceptance on the available platform
- [x] Clean source full and drop-in packages

## Native Windows final gate

- [ ] Run `BUILD_WINDOWS.bat` on Windows 10/11
- [ ] Confirm automated report ends in `FINAL_RESULT=PASS`
- [ ] Run `RUN_WINDOWS_MANUAL_ACCEPTANCE.bat`
- [ ] Confirm operator report ends in `final_result=PASS`
- [ ] Run `PROMOTE_WINDOWS_V1.bat`
- [ ] Confirm final V1 ZIP, checksum, and final manifest exist
