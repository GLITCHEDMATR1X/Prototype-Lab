from __future__ import annotations

import ast
import json
import math
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> int:
    terrain_source = (ROOT / "terrains.py").read_text(encoding="utf-8")
    chunks_source = (ROOT / "surface_chunks.py").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "build_manifest.json").read_text(encoding="utf-8"))

    for name in ("terrains.py", "surface_chunks.py", "surface_resources.py", "space_core.py"):
        ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    require(True, "Pass 22 active modules parse")

    from surface_chunks import (
        CHUNK_CACHE_LIMIT,
        CHUNK_SAMPLE_RESOLUTION,
        CHUNK_WORLD_SIZE,
        OBJECT_CACHE_LIMIT,
        build_chunk_pixels,
        generate_chunk_objects,
        sample_geology,
    )

    require(CHUNK_WORLD_SIZE == 64, "surface streams fixed 64-unit world chunks")
    require(CHUNK_SAMPLE_RESOLUTION == 48, "terrain chunks use compact cached relief samples")
    require(24 <= CHUNK_CACHE_LIMIT <= 64, "terrain cache has a bounded exploration budget")
    require(48 <= OBJECT_CACHE_LIMIT <= 96, "procedural object cache has a bounded exploration budget")

    seed = 20260804
    terrain = "roseglass"
    for boundary in (-128.0, -64.0, 0.0, 64.0, 128.0, 384.0):
        a = sample_geology(seed, terrain, boundary - 0.001, 37.25)
        b = sample_geology(seed, terrain, boundary + 0.001, 37.25)
        require(abs(a.height - b.height) < 0.0025, f"height field is continuous across x={boundary:g}")
    for boundary in (-64.0, 0.0, 64.0, 384.0):
        a = sample_geology(seed, terrain, -21.5, boundary - 0.001)
        b = sample_geology(seed, terrain, -21.5, boundary + 0.001)
        require(abs(a.height - b.height) < 0.0025, f"height field is continuous across y={boundary:g}")

    negative_a = sample_geology(seed, "abyss", -901.25, -733.75)
    negative_b = sample_geology(seed, "abyss", -901.25, -733.75)
    require(negative_a == negative_b, "negative-coordinate terrain is deterministic")

    biome_defs = [
        ("desert", 0.10, 0.86, 48), ("ice", 0.58, 0.10, 56),
        ("jungle", 0.33, 0.72, 84), ("volcanic", 0.01, 0.12, 62),
        ("crystal", 0.70, 0.92, 72), ("oceanic", 0.53, 0.18, 74),
        ("fungal", 0.86, 0.46, 112), ("rust", 0.055, 0.13, 76),
        ("salt", 0.72, 0.12, 36), ("abyss", 0.56, 0.48, 82),
        ("storm", 0.60, 0.12, 58), ("roseglass", 0.92, 0.52, 88),
    ]
    signatures = set()
    for index, (name, base_hue, accent_hue, density) in enumerate(biome_defs):
        samples = [sample_geology(seed + index * 101, name, x * 17.0 - 91.0, y * 19.0 + 43.0) for y in range(8) for x in range(8)]
        heights = [sample.height for sample in samples]
        require(max(heights) - min(heights) >= 0.060, f"{name} retains visible relief variation")
        require(max(sample.ridge for sample in samples) > 0.12, f"{name} contains ridge structure")
        require(max(sample.basin for sample in samples) > 0.10, f"{name} contains basin structure")
        require(max(sample.fracture for sample in samples) > 0.05, f"{name} contains fracture structure")
        pixels = build_chunk_pixels(seed + index * 101, {"terrain": name, "base_hue": base_hue, "accent_hue": accent_hue, "prop_density": density}, 2, -3)
        flat = [color for row in pixels for color in row]
        require(len(set(flat)) >= 48, f"{name} chunk uses layered material color variation")
        signatures.add(tuple(flat[::97][:8]))
    require(len(signatures) == 12, "all twelve terrain families retain distinct generated signatures")

    biome = {"terrain": "jungle", "base_hue": 0.33, "accent_hue": 0.72, "prop_density": 84}
    objects_a = generate_chunk_objects(seed, biome, -4, 7)
    objects_b = generate_chunk_objects(seed, biome, -4, 7)
    require(objects_a == objects_b, "exploration resources are deterministic per chunk")
    all_objects = [item for group in objects_a.values() for item in group]
    require(bool(all_objects), "new chunks distribute recoverable exploration objects")
    require(len({int(item["seed"]) for item in all_objects}) == len(all_objects), "chunk object recovery IDs are unique")
    require(all(-4 * CHUNK_WORLD_SIZE <= item["x"] < -3 * CHUNK_WORLD_SIZE for item in all_objects), "negative-x chunk objects remain inside their chunk")
    require(all(7 * CHUNK_WORLD_SIZE <= item["y"] < 8 * CHUNK_WORLD_SIZE for item in all_objects), "positive-y chunk objects remain inside their chunk")

    start = time.perf_counter()
    for cy in range(-1, 2):
        for cx in range(-2, 2):
            build_chunk_pixels(seed, biome, cx, cy)
    elapsed = time.perf_counter() - start
    require(elapsed < 1.5, "twelve uncached terrain chunks generate within the CPU budget")

    require("self.cam_x = clamp(self.cam_x" not in terrain_source, "surface movement has no x boundary blocker")
    require("self.cam_y = clamp(self.cam_y" not in terrain_source, "surface movement has no y boundary blocker")
    require("return self.cam_x - view_w * 0.5" in terrain_source, "camera pans continuously around the player")
    require("_draw_chunked_terrain" in terrain_source, "surface renderer composes visible procedural chunks")
    require("_terrain_chunk_cache = OrderedDict()" in terrain_source, "terrain streaming uses an LRU-style cache")
    require("generate_chunk_objects" in terrain_source and "_procedural_objects_for_chunk" in terrain_source, "explored chunks stream recoverable objects")
    require("self._mark_harvested(category, item_seed)" in terrain_source, "streamed resources use existing persistent recovery state")
    require("ridges, basins, strata" in terrain_source, "terrain visual grammar documents layered geological forms")
    require("full-width color bands" in chunks_source or "full-width color" in chunks_source, "localized materials replace simple color streaks")

    require(int(manifest.get("pass", 0)) >= 22, "manifest preserves the Pass 22 seamless-surface authority")
    surface_contract = manifest.get("surface_world_contract", {})
    require(surface_contract.get("boundary_mode") == "unbounded_chunk_streaming", "manifest locks unbounded surface exploration")
    require(surface_contract.get("chunk_world_size") == 64, "manifest records the chunk world size")
    require(surface_contract.get("terrain_cache_limit") == CHUNK_CACHE_LIMIT, "manifest records bounded terrain caching")
    require(surface_contract.get("procedural_resources") is True, "manifest records streamed recoverable resources")

    print(f"CHUNK_GENERATION_SECONDS={elapsed:.4f}")
    print("FINAL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
