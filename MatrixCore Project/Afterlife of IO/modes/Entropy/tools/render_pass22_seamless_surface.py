from __future__ import annotations

import ast
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from surface_chunks import CHUNK_WORLD_SIZE, TERRAIN_TEXELS_PER_UNIT, build_chunk_pixels, generate_chunk_objects

VIEW_W = 160.0
VIEW_H = 90.0
SCREEN = (1920, 1080)
INTERNAL = (int(VIEW_W * TERRAIN_TEXELS_PER_UNIT), int(VIEW_H * TERRAIN_TEXELS_PER_UNIT))


def load_biomes() -> list[dict]:
    tree = ast.parse((ROOT / "terrains.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "BIOMES" for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("BIOMES not found")


BIOMES = {item["terrain"]: item for item in load_biomes()}


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


F16 = font(16)
F20 = font(20)
F24 = font(24)
F28B = font(28, True)
F34B = font(34, True)


def paste_clipped(dst: Image.Image, src: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(dst.width, x + src.width)
    bottom = min(dst.height, y + src.height)
    if right <= left or bottom <= top:
        return
    crop = src.crop((left - x, top - y, right - x, bottom - y))
    dst.paste(crop, (left, top))


def world_to_internal(x: float, y: float, left: float, top: float) -> tuple[int, int]:
    return int(round((x - left) * TERRAIN_TEXELS_PER_UNIT)), int(round((y - top) * TERRAIN_TEXELS_PER_UNIT))


def compose_internal(seed: int, biome: dict, cam_x: float, cam_y: float) -> tuple[Image.Image, list[dict]]:
    left = cam_x - VIEW_W * 0.5
    top = cam_y - VIEW_H * 0.5
    image = Image.new("RGB", INTERNAL, (4, 7, 12))
    min_cx = math.floor(left / CHUNK_WORLD_SIZE)
    min_cy = math.floor(top / CHUNK_WORLD_SIZE)
    max_cx = math.floor((left + VIEW_W) / CHUNK_WORLD_SIZE)
    max_cy = math.floor((top + VIEW_H) / CHUNK_WORLD_SIZE)
    visible_objects: list[dict] = []
    target_size = CHUNK_WORLD_SIZE * TERRAIN_TEXELS_PER_UNIT
    for cy in range(min_cy, max_cy + 1):
        for cx in range(min_cx, max_cx + 1):
            pixels = build_chunk_pixels(seed, biome, cx, cy)
            tile = Image.new("RGB", (len(pixels[0]), len(pixels)))
            tile.putdata([color for row in pixels for color in row])
            tile = tile.resize((target_size, target_size), Image.Resampling.BICUBIC)
            dx = int(round((cx * CHUNK_WORLD_SIZE - left) * TERRAIN_TEXELS_PER_UNIT))
            dy = int(round((cy * CHUNK_WORLD_SIZE - top) * TERRAIN_TEXELS_PER_UNIT))
            paste_clipped(image, tile, dx, dy)
            generated = generate_chunk_objects(seed, biome, cx, cy)
            for key, category in (("trees", "tree"), ("plants", "plant"), ("props", "prop")):
                for item in generated[key]:
                    item = dict(item)
                    item["category"] = category
                    visible_objects.append(item)
    return image, visible_objects


def render_surface(seed: int, terrain: str, cam_x: float, cam_y: float, filename: str, subtitle: str) -> Path:
    biome = BIOMES[terrain]
    internal, objects = compose_internal(seed, biome, cam_x, cam_y)
    image = internal.resize(SCREEN, Image.Resampling.NEAREST).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    left = cam_x - VIEW_W * 0.5
    top = cam_y - VIEW_H * 0.5
    sx_scale = SCREEN[0] / VIEW_W
    sy_scale = SCREEN[1] / VIEW_H

    # Restrained navigation lattice, matching the live renderer's 32-unit spacing.
    start_x = math.floor(left / 32.0) * 32
    start_y = math.floor(top / 32.0) * 32
    for gx in range(int(start_x), int(left + VIEW_W) + 32, 32):
        sx = int((gx - left) * sx_scale)
        draw.line((sx, 0, sx, SCREEN[1]), fill=(126, 218, 228, 10), width=1)
    for gy in range(int(start_y), int(top + VIEW_H) + 32, 32):
        sy = int((gy - top) * sy_scale)
        draw.line((0, sy, SCREEN[0], sy), fill=(126, 218, 228, 10), width=1)

    tree_col = (72, 152, 116, 255)
    plant_col = (156, 226, 188, 255)
    for item in objects:
        x = (item["x"] - left) * sx_scale
        y = (item["y"] - top) * sy_scale
        if not (-20 <= x <= SCREEN[0] + 20 and -20 <= y <= SCREEN[1] + 20):
            continue
        if item["category"] == "tree":
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(7, 13, 17, 220))
            draw.ellipse((x - 6, y - 8, x + 6, y + 4), fill=tree_col)
        elif item["category"] == "plant":
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=plant_col)
        else:
            draw.rounded_rectangle((x - 5, y - 5, x + 5, y + 5), radius=2, fill=(18, 24, 32, 255), outline=(154, 186, 198, 255), width=1)

    # Player remains centered while the world pans.
    px, py = SCREEN[0] // 2, SCREEN[1] // 2
    draw.ellipse((px - 25, py + 20, px + 25, py + 38), fill=(4, 8, 12, 220))
    draw.ellipse((px - 35, py - 35, px + 35, py + 35), outline=(82, 238, 232, 230), width=2)
    draw.polygon(((px, py - 24), (px - 15, py + 16), (px + 15, py + 16)), fill=(232, 250, 252, 255), outline=(82, 238, 232, 255))
    draw.line((px, py, px, py - 44), fill=(112, 244, 238, 255), width=2)

    # Distant central objective direction remains readable during free exploration.
    objective_x, objective_y = 210.0, 205.0
    dx = objective_x - cam_x
    dy = objective_y - cam_y
    length = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / length, dy / length
    ex = int(max(74, min(SCREEN[0] - 74, px + ux * 440)))
    ey = int(max(130, min(SCREEN[1] - 110, py + uy * 310)))
    rx, ry = -uy, ux
    points = [
        (ex + ux * 18, ey + uy * 18),
        (ex - ux * 10 + rx * 10, ey - uy * 10 + ry * 10),
        (ex - ux * 10 - rx * 10, ey - uy * 10 - ry * 10),
    ]
    draw.polygon(points, fill=(255, 214, 112, 255))
    draw.ellipse((ex - 24, ey - 24, ex + 24, ey + 24), outline=(4, 8, 12, 230), width=2)

    region_x = math.floor(cam_x / CHUNK_WORLD_SIZE)
    region_y = math.floor(cam_y / CHUNK_WORLD_SIZE)
    panel_w = 760
    panel_h = 102
    draw.rounded_rectangle((48, 36, 48 + panel_w, 36 + panel_h), radius=8, fill=(5, 8, 14, 188), outline=(55, 92, 112, 255), width=1)
    draw.text((64, 48), f"{biome['name']}  /  {terrain.upper()}", font=F24, fill=(232, 242, 248, 255))
    draw.text((64, 76), f"SEAMLESS SURFACE  /  REGION {region_x:+d},{region_y:+d}  /  EXPLORE", font=F20, fill=(138, 222, 226, 255))
    draw.text((64, 104), f"RELIC CORE SIGNAL  /  {length:03.0f}m", font=F20, fill=(255, 214, 112, 255))

    caption = Image.new("RGBA", (860, 70), (5, 8, 14, 210))
    cap_draw = ImageDraw.Draw(caption)
    cap_draw.text((18, 9), subtitle, font=F20, fill=(232, 242, 248, 255))
    cap_draw.text((18, 38), f"WORLD COORDINATE  {cam_x:+.1f}, {cam_y:+.1f}", font=F16, fill=(138, 222, 226, 255))
    image.alpha_composite(caption, (SCREEN[0] - 908, SCREEN[1] - 106))

    path = OUT / filename
    image.convert("RGB").save(path, quality=94)
    return path


def render_gallery(filename: str) -> Path:
    canvas = Image.new("RGB", SCREEN, (3, 6, 11))
    draw = ImageDraw.Draw(canvas)
    draw.text((58, 34), "PASS 22  /  GEOLOGICAL TERRAIN GRAMMAR", font=F34B, fill=(236, 244, 248))
    draw.text((58, 78), "Ridges, basins, strata, faults, and localized deposits replace simple color streaks.", font=F20, fill=(138, 222, 226))
    terrains = ["desert", "ice", "volcanic", "fungal"]
    positions = [(48, 132), (984, 132), (48, 598), (984, 598)]
    for index, (terrain, (ox, oy)) in enumerate(zip(terrains, positions)):
        biome = BIOMES[terrain]
        internal, _ = compose_internal(20260804 + index * 731, biome, 544.0 + index * 173.0, -122.0 + index * 97.0)
        panel = internal.resize((888, 400), Image.Resampling.NEAREST)
        canvas.paste(panel, (ox, oy))
        draw.rounded_rectangle((ox, oy, ox + 888, oy + 400), radius=8, outline=(74, 122, 140), width=2)
        draw.rectangle((ox, oy + 344, ox + 888, oy + 400), fill=(4, 8, 14, 210))
        draw.text((ox + 20, oy + 354), f"{biome['name']}  /  {terrain.upper()}", font=F24, fill=(236, 244, 248))
        draw.text((ox + 20, oy + 382), "absolute-coordinate relief / cached procedural chunks", font=F16, fill=(138, 222, 226))
    path = OUT / filename
    canvas.save(path, quality=94)
    return path


def contact_sheet(paths: list[Path], filename: str) -> Path:
    canvas = Image.new("RGB", SCREEN, (2, 5, 10))
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 28), "ENTROPY PASS 22  /  SEAMLESS PROCEDURAL PLANETARY SURFACE", font=F28B, fill=(236, 244, 248))
    draw.text((48, 66), "The player-centered camera crosses the old map extent and negative world coordinates without a terrain reset.", font=F16, fill=(138, 222, 226))
    first = Image.open(paths[0]).resize((896, 504), Image.Resampling.LANCZOS)
    second = Image.open(paths[1]).resize((896, 504), Image.Resampling.LANCZOS)
    gallery = Image.open(paths[2]).resize((1792, 504), Image.Resampling.LANCZOS)
    canvas.paste(first, (48, 108))
    canvas.paste(second, (976, 108))
    canvas.paste(gallery, (48, 640))
    draw.rectangle((48, 108, 944, 612), outline=(64, 110, 126), width=2)
    draw.rectangle((976, 108, 1872, 612), outline=(64, 110, 126), width=2)
    draw.rectangle((48, 640, 1840, 1078), outline=(64, 110, 126), width=2)
    draw.text((66, 116), "FORMER EAST EDGE CROSSED", font=F16, fill=(255, 214, 112))
    draw.text((994, 116), "NEGATIVE WORLD REGIONS", font=F16, fill=(255, 214, 112))
    path = OUT / filename
    canvas.save(path, quality=94)
    return path


def main() -> int:
    east = render_surface(20260804, "jungle", 428.0, 214.0, "Entropy_Pass22_SeamlessEast_Proof.png", "FORMER 384-UNIT EAST EDGE IS BEHIND THE PLAYER")
    negative = render_surface(20260804 ^ 0x5A17, "roseglass", -174.0, -102.0, "Entropy_Pass22_NegativeRegion_Proof.png", "NEGATIVE REGIONS STREAM FROM THE SAME WORLD FIELD")
    gallery = render_gallery("Entropy_Pass22_GeologyGallery_Proof.png")
    sheet = contact_sheet([east, negative, gallery], "Entropy_Pass22_contact_sheet.png")
    print(east)
    print(negative)
    print(gallery)
    print(sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
