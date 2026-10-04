# Vector Wars Pass 16 — Combat Difficulty Authority

STATUS: CANDIDATE
VISUAL ACCEPTANCE: PENDING (no rendering changes in this pass; pygame-ce runtime unavailable in this container)
TARGET-RUNTIME TEST: NOT RUN

## Single task

Decouple combat difficulty from renderer/performance presets before further pacing and speed tuning.

## Problem found during the required Pass 15 recheck

`PERF_CAPS` controlled both rendering budgets and live combat populations. Selecting `--perf low`, `smooth`, `balanced`, or `quality` therefore changed the number of street threats, fighters, UFOs, warships, and helicopters. A graphics/performance choice was silently functioning as a difficulty setting.

## Fix

Added `gameplay_balance.py` as the gameplay-population authority.

The Standard population preserves the previous default `smooth` experience:

- street threats: 30
- fighters: 10
- UFOs: 3
- warships: 5
- helicopters: 2

`PERF_CAPS` now owns rendering/performance quantities only. Low/balanced/quality may change draw/object budgets but no longer alter those combat populations.

## Reference basis

Microsoft Xbox Accessibility Guideline 108 treats enemy quantity as a difficulty variable and recommends deliberate, player-understandable difficulty configuration rather than unrelated hidden changes:
https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/108

Microsoft Accessibility Feature Tags likewise identifies enemy count, health, damage, lives, resources, and AI as variables that can define difficulty and says differences between difficulty settings should be described:
https://learn.microsoft.com/en-us/xbox/accessibility/accessibility-feature-tags

Real-world speed references are recorded for the later vehicle/pacing pass, but are intentionally not applied here. USAF F-16 references list approximately Mach 2 / 1,500 mph at altitude, while the U.S. Navy lists Arleigh Burke-class destroyers at over 30 knots. These establish useful relative-scale anchors, not literal game-unit conversions:
https://www.944fw.afrc.af.mil/About-Us/Fact-Sheets/Display/Article/189493/f-16-fighting-falcon/
https://www.navy.mil/Resources/Fact-Files/Display-FactFiles/Article/2169871/destroyers-ddg-51/

## Regression additions

- `tools/test_gameplay_balance.py`
  - locks the Standard combat population
  - verifies every campaign objective remains fieldable
- `tools/test_pass16_difficulty_authority.py`
  - rejects combat-population ownership inside `PERF_CAPS`
  - verifies `main.py` reads all five populations from gameplay authority

## Validation

Source-tree authoritative regression suite: 21/21 PASS.

No HUD, rendering, combat damage, weapon rate, mission target count, progression, save, music, or HoloVerse behavior was intentionally changed.
