#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'main.py').read_text(encoding='utf-8')

def require(label: str, condition: bool):
    assert condition, label
    print(f'PASS {label}')

# The renderer-performance table must not own combat populations anymore.
tree = ast.parse(source)
perf_keys = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'PERF_CAPS' and isinstance(node.value, ast.Dict):
                for profile in node.value.values:
                    if isinstance(profile, ast.Dict):
                        for key in profile.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                perf_keys.add(key.value)
require('performance profiles do not own traffic count', 'traffic' not in perf_keys)
require('performance profiles do not own fighter count', 'ai' not in perf_keys)
require('performance profiles do not own UFO count', 'ufo' not in perf_keys)
require('performance profiles do not own warship count', 'warships' not in perf_keys)
require('performance profiles do not own helicopter count', 'helis' not in perf_keys)

require('ground traffic uses gameplay authority', 'TRAFFIC_TARGET_COUNT = standard_count("traffic")' in source)
require('air fighters use gameplay authority', 'AI_COUNT = standard_count("fighters")' in source)
require('air UFOs use gameplay authority', 'UFO_COUNT = standard_count("ufos")' in source)
require('ocean warships use gameplay authority', 'OCEAN_WARSHIP_COUNT = standard_count("warships")' in source)
require('ocean helicopters use gameplay authority', 'OCEAN_HELI_LIMIT = standard_count("helicopters")' in source)

print('pass16_difficulty_authority: PASS')
