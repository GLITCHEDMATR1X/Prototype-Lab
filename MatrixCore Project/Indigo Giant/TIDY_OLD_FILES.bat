@echo off
setlocal
cd /d "%~dp0"
title The Indigo Giant - Pass 62 tidy

rem Pass 62: moves the old top-level files into their new homes, and the old copies into
rem _to_delete\pass62\. It never deletes anything, uses no wildcards, and never touches
rem controls.json or your saves. To undo, move the files back out of _to_delete\pass62\.

if not exist "indigo_giant\app.py" (
    echo The new game files are not here yet ^(indigo_giant\app.py is missing^). Nothing was moved.
    pause
    exit /b 1
)
findstr /c:"indigo_giant" "main.py" >nul 2>nul
if errorlevel 1 (
    echo main.py is still the old one. Nothing was moved.
    pause
    exit /b 1
)

if not exist "_to_delete\pass62" mkdir "_to_delete\pass62"
if not exist "docs\pass_notes" mkdir "docs\pass_notes"
set "LOG=_to_delete\pass62\moved.txt"
echo Pass 62 tidy, %DATE% %TIME%> "%LOG%"
set /a MOVED=0

echo Moving notes, screenshots and the animation map into docs\ ...
call :move "PASS49_FIXES_BALANCE_NOTE.txt" "docs\pass_notes\PASS49_FIXES_BALANCE_NOTE.txt"
call :move "PASS50_FIRST_LAUNCH_NOTE.txt" "docs\pass_notes\PASS50_FIRST_LAUNCH_NOTE.txt"
call :move "PASS51_DEEP_DESERT_NOTE.txt" "docs\pass_notes\PASS51_DEEP_DESERT_NOTE.txt"
call :move "PASS52_FEET_MATCH_GROUND_NOTE.txt" "docs\pass_notes\PASS52_FEET_MATCH_GROUND_NOTE.txt"
call :move "PASS53_GIANT_STAMINA_NOTE.txt" "docs\pass_notes\PASS53_GIANT_STAMINA_NOTE.txt"
call :move "PASS54_POLISH_NOTE.txt" "docs\pass_notes\PASS54_POLISH_NOTE.txt"
call :move "PASS55_WALK_IN_SHELTERS_NOTE.txt" "docs\pass_notes\PASS55_WALK_IN_SHELTERS_NOTE.txt"
call :move "PASS56_NATURAL_MOUTH_NOTE.txt" "docs\pass_notes\PASS56_NATURAL_MOUTH_NOTE.txt"
call :move "PASS57_BUILD_REVIEW_NOTE.txt" "docs\pass_notes\PASS57_BUILD_REVIEW_NOTE.txt"
call :move "PASS58_LOOK_FOOTPRINTS_PACE_FIGHT_NOTE.txt" "docs\pass_notes\PASS58_LOOK_FOOTPRINTS_PACE_FIGHT_NOTE.txt"
call :move "PASS59_INDIGO_GLOW_NOTE.txt" "docs\pass_notes\PASS59_INDIGO_GLOW_NOTE.txt"
call :move "PASS60_CRIMSON_POWERS_NOTE.txt" "docs\pass_notes\PASS60_CRIMSON_POWERS_NOTE.txt"
call :move "PASS61_NYX_ORBIT_GLEEBS_NOTE.txt" "docs\pass_notes\PASS61_NYX_ORBIT_GLEEBS_NOTE.txt"
call :move "ANIMATION_MAP.md" "docs\ANIMATION_MAP.md"
call :move "screenshots" "docs\screenshots"

echo Moving the old copies into _to_delete\pass62\ ...
call :move "audio.py" "_to_delete\pass62\audio.py"
call :move "controls.py" "_to_delete\pass62\controls.py"
call :move "crimson.py" "_to_delete\pass62\crimson.py"
call :move "daycycle.py" "_to_delete\pass62\daycycle.py"
call :move "desert.py" "_to_delete\pass62\desert.py"
call :move "desert_geom.py" "_to_delete\pass62\desert_geom.py"
call :move "desert_world.py" "_to_delete\pass62\desert_world.py"
call :move "endgame.py" "_to_delete\pass62\endgame.py"
call :move "fight.py" "_to_delete\pass62\fight.py"
call :move "flora.py" "_to_delete\pass62\flora.py"
call :move "frontend.py" "_to_delete\pass62\frontend.py"
call :move "gleebs.py" "_to_delete\pass62\gleebs.py"
call :move "glow.py" "_to_delete\pass62\glow.py"
call :move "gltf_idle.py" "_to_delete\pass62\gltf_idle.py"
call :move "hud.py" "_to_delete\pass62\hud.py"
call :move "journey.py" "_to_delete\pass62\journey.py"
call :move "locomotion.py" "_to_delete\pass62\locomotion.py"
call :move "lore.py" "_to_delete\pass62\lore.py"
call :move "places.py" "_to_delete\pass62\places.py"
call :move "places_geom.py" "_to_delete\pass62\places_geom.py"
call :move "savegame.py" "_to_delete\pass62\savegame.py"
call :move "settings.py" "_to_delete\pass62\settings.py"
call :move "skinned_actor.py" "_to_delete\pass62\skinned_actor.py"
call :move "sky.py" "_to_delete\pass62\sky.py"
call :move "survival.py" "_to_delete\pass62\survival.py"
call :move "teach.py" "_to_delete\pass62\teach.py"
call :move "wild.py" "_to_delete\pass62\wild.py"
call :move "tools_discovery_probe.py" "_to_delete\pass62\tools_discovery_probe.py"
call :move "tools_make_placeholder_audio.py" "_to_delete\pass62\tools_make_placeholder_audio.py"
call :move "tools_pass38_check.py" "_to_delete\pass62\tools_pass38_check.py"
call :move "tools_pass39_check.py" "_to_delete\pass62\tools_pass39_check.py"
call :move "tools_pass40_check.py" "_to_delete\pass62\tools_pass40_check.py"
call :move "tools_pass41_controls_check.py" "_to_delete\pass62\tools_pass41_controls_check.py"
call :move "tools_pass42_world_check.py" "_to_delete\pass62\tools_pass42_world_check.py"
call :move "tools_pass43_loop_check.py" "_to_delete\pass62\tools_pass43_loop_check.py"
call :move "tools_pass44_check.py" "_to_delete\pass62\tools_pass44_check.py"
call :move "tools_pass45_check.py" "_to_delete\pass62\tools_pass45_check.py"
call :move "tools_pass46_check.py" "_to_delete\pass62\tools_pass46_check.py"
call :move "tools_pass47_check.py" "_to_delete\pass62\tools_pass47_check.py"
call :move "tools_pass48_check.py" "_to_delete\pass62\tools_pass48_check.py"
call :move "tools_pass49_check.py" "_to_delete\pass62\tools_pass49_check.py"
call :move "tools_pass50_check.py" "_to_delete\pass62\tools_pass50_check.py"
call :move "tools_pass51_check.py" "_to_delete\pass62\tools_pass51_check.py"
call :move "tools_pass52_check.py" "_to_delete\pass62\tools_pass52_check.py"
call :move "tools_pass53_check.py" "_to_delete\pass62\tools_pass53_check.py"
call :move "tools_pass54_check.py" "_to_delete\pass62\tools_pass54_check.py"
call :move "tools_pass55_check.py" "_to_delete\pass62\tools_pass55_check.py"
call :move "tools_pass56_check.py" "_to_delete\pass62\tools_pass56_check.py"
call :move "tools_pass57_check.py" "_to_delete\pass62\tools_pass57_check.py"
call :move "tools_pass58_check.py" "_to_delete\pass62\tools_pass58_check.py"
call :move "tools_pass59_check.py" "_to_delete\pass62\tools_pass59_check.py"
call :move "tools_pass60_check.py" "_to_delete\pass62\tools_pass60_check.py"
call :move "tools_pass61_check.py" "_to_delete\pass62\tools_pass61_check.py"
call :move "tools_playthrough.py" "_to_delete\pass62\tools_playthrough.py"
call :move "perf_probe.py" "_to_delete\pass62\perf_probe.py"
call :move "animation_audit.py" "_to_delete\pass62\animation_audit.py"
call :move "animation_audit.csv" "_to_delete\pass62\animation_audit.csv"
call :move "INDIGO_DIAGNOSTIC.py" "_to_delete\pass62\INDIGO_DIAGNOSTIC.py"
call :move "RUN_INDIGO_DIAGNOSTIC.bat" "_to_delete\pass62\RUN_INDIGO_DIAGNOSTIC.bat"
call :move "indigo_diagnostic.log" "_to_delete\pass62\indigo_diagnostic.log"
call :move "validation.txt" "_to_delete\pass62\validation.txt"
call :move "app.py" "_to_delete\pass62\app.py"
call :move "__pycache__" "_to_delete\pass62\__pycache__"

echo.
echo Done: %MOVED% moved. The list is in %LOG%
echo Start the game from the Prototype Lab or RUN_INDIGO_GIANT.bat to check it.
echo When you are happy, you can delete the _to_delete folder.
pause
rem this script has done its job: it moves itself into _to_delete\pass62\ too
(goto) 2>nul & move "%~f0" "%~dp0_to_delete\pass62\" >nul

:move
if not exist "%~1" goto :eof
if exist "%~2" (
    echo   skipped %~1 ^(already at %~2^)
    echo skipped %~1 - already at %~2>> "%LOG%"
    goto :eof
)
move "%~1" "%~2" >nul
if errorlevel 1 (
    echo   COULD NOT MOVE %~1
    echo FAILED %~1>> "%LOG%"
    goto :eof
)
echo   %~1  -^>  %~2
echo %~1 -^> %~2>> "%LOG%"
set /a MOVED+=1
goto :eof
