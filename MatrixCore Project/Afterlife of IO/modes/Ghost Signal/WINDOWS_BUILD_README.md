# Windows V1 RC3 Build and Final Promotion

Run `BUILD_WINDOWS.bat` on native Windows 10 or 11.

The build script:

1. Creates or reuses `.venv`.
2. Installs the pinned runtime and PyInstaller dependencies.
3. Runs profile migration, campaign, Windows-gate contract, and full source validation.
4. Builds a portable PyInstaller **onedir** package.
5. Runs executable checks for windowed/fullscreen screenshots, audio/no-audio launch, input, blank-save, migrated-save, persistence, result packets, crash logs, and the manual-assistant contract.
6. Creates `release/Ghost_Signal_Utopia_ChapterOne_V1_RC3_Windows.zip` and its SHA-256 file.

Then run:

```text
RUN_WINDOWS_MANUAL_ACCEPTANCE.bat
PROMOTE_WINDOWS_V1.bat
```

The first command launches an operator-guided native Windows test. The second command refuses final promotion unless both the automated report and operator report pass. Successful promotion creates:

```text
release/Ghost_Signal_Utopia_ChapterOne_V1_Windows.zip
release/Ghost_Signal_Utopia_ChapterOne_V1_Windows_SHA256.txt
release/Ghost_Signal_Utopia_ChapterOne_V1_FINAL_MANIFEST.json
```

Campaign saves remain outside the build under `%LOCALAPPDATA%\GhostSignalUtopia`.
