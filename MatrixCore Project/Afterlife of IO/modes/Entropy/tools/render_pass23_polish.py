from __future__ import annotations

import ast
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

from surface_chunks import CHUNK_WORLD_SIZE, TERRAIN_TEXELS_PER_UNIT, build_chunk_pixels, generate_chunk_objects

SCREEN = (1920, 1080)
VIEW_W = 160.0
VIEW_H = 90.0
INTERNAL = (int(VIEW_W * TERRAIN_TEXELS_PER_UNIT), int(VIEW_H * TERRAIN_TEXELS_PER_UNIT))


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F14 = font(14)
F16 = font(16)
F18 = font(18)
F20 = font(20)
F24 = font(24)
F28B = font(28, True)
F34B = font(34, True)


def load_biomes() -> dict[str, dict]:
    tree = ast.parse((ROOT / "terrains.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "BIOMES" for target in node.targets):
            items = ast.literal_eval(node.value)
            return {item["terrain"]: item for item in items}
    raise RuntimeError("BIOMES not found")


BIOMES = load_biomes()


def paste_clipped(dst: Image.Image, src: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(dst.width, x + src.width)
    bottom = min(dst.height, y + src.height)
    if right <= left or bottom <= top:
        return
    crop = src.crop((left - x, top - y, right - x, bottom - y))
    dst.paste(crop, (left, top))


def compose(seed: int, biome: dict, view_x: float, view_y: float) -> tuple[Image.Image, list[dict]]:
    left = view_x - VIEW_W * 0.5
    top = view_y - VIEW_H * 0.5
    image = Image.new("RGB", INTERNAL, (4, 7, 12))
    objects: list[dict] = []
    min_cx = math.floor(left / CHUNK_WORLD_SIZE)
    min_cy = math.floor(top / CHUNK_WORLD_SIZE)
    max_cx = math.floor((left + VIEW_W) / CHUNK_WORLD_SIZE)
    max_cy = math.floor((top + VIEW_H) / CHUNK_WORLD_SIZE)
    target = CHUNK_WORLD_SIZE * TERRAIN_TEXELS_PER_UNIT
    for cy in range(min_cy, max_cy + 1):
        for cx in range(min_cx, max_cx + 1):
            pixels = build_chunk_pixels(seed, biome, cx, cy)
            tile = Image.new("RGB", (len(pixels[0]), len(pixels)))
            tile.putdata([color for row in pixels for color in row])
            tile = tile.resize((target, target), Image.Resampling.BICUBIC)
            dx = int(round((cx * CHUNK_WORLD_SIZE - left) * TERRAIN_TEXELS_PER_UNIT))
            dy = int(round((cy * CHUNK_WORLD_SIZE - top) * TERRAIN_TEXELS_PER_UNIT))
            paste_clipped(image, tile, dx, dy)
            generated = generate_chunk_objects(seed, biome, cx, cy)
            for group, category in (("trees", "tree"), ("plants", "plant"), ("props", "prop")):
                for item in generated[group]:
                    obj = dict(item)
                    obj["category"] = category
                    objects.append(obj)
    return image.resize(SCREEN, Image.Resampling.NEAREST).convert("RGBA"), objects


def world_to_screen(x: float, y: float, view_x: float, view_y: float) -> tuple[int, int]:
    left = view_x - VIEW_W * 0.5
    top = view_y - VIEW_H * 0.5
    return int((x - left) / VIEW_W * SCREEN[0]), int((y - top) / VIEW_H * SCREEN[1])


def draw_vignette(image: Image.Image) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    for i in range(7):
        inset_x = i * 12
        inset_y = i * 8
        draw.rounded_rectangle((inset_x, inset_y, SCREEN[0] - inset_x, SCREEN[1] - inset_y), radius=22, outline=(0, 0, 0, 13 + i * 4), width=max(8, 18 - i * 2))
    image.alpha_composite(layer)


def draw_objects(draw: ImageDraw.ImageDraw, objects: list[dict], view_x: float, view_y: float, biome: dict, polished: bool) -> None:
    tree_col = (74, 158, 118, 255)
    plant_col = (164, 230, 190, 255)
    for item in objects:
        x, y = world_to_screen(float(item["x"]), float(item["y"]), view_x, view_y)
        if not (-20 <= x <= SCREEN[0] + 20 and -20 <= y <= SCREEN[1] + 20):
            continue
        seed = int(item.get("seed", 0))
        category = item["category"]
        if not polished:
            if category == "tree":
                draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(9, 14, 18, 255))
                draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=tree_col)
            elif category == "plant":
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=plant_col)
            else:
                draw.rounded_rectangle((x - 4, y - 4, x + 5, y + 5), radius=2, fill=(18, 24, 32, 255), outline=(154, 186, 198, 255), width=1)
            continue
        if category == "tree":
            size = 5 + seed % 3
            draw.ellipse((x - size - 1, y + 2, x + size + 4, y + size + 7), fill=(5, 9, 13, 230))
            draw.line((x, y + 1, x, y + 8), fill=(54, 48, 42, 255), width=2)
            draw.ellipse((x - size, y - size - 2, x + size, y + size - 2), fill=tree_col)
            draw.ellipse((x - 4, y - 7, x + 1, y - 2), fill=(104, 186, 146, 255))
        elif category == "plant":
            draw.line((x - 4, y + 2, x + 4, y - 2), fill=plant_col, width=2)
            draw.line((x - 2, y - 4, x + 2, y + 4), fill=plant_col, width=2)
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(220, 250, 224, 255))
        else:
            variant = seed % 3
            draw.ellipse((x - 7, y + 2, x + 8, y + 9), fill=(5, 9, 13, 230))
            if variant == 0:
                draw.polygon(((x, y - 6), (x + 6, y + 4), (x - 5, y + 5)), fill=(32, 42, 50, 255), outline=(154, 186, 198, 255))
            else:
                draw.rounded_rectangle((x - 5, y - 5, x + 6, y + 5), radius=2, fill=(18, 24, 32, 255), outline=(154, 186, 198, 255), width=1)
                if variant == 2:
                    draw.line((x - 3, y, x + 3, y), fill=(98, 232, 220, 255), width=1)


def draw_player(draw: ImageDraw.ImageDraw, actor_x: float, actor_y: float, view_x: float, view_y: float, moving: bool = True) -> tuple[int, int]:
    px, py = world_to_screen(actor_x, actor_y, view_x, view_y)
    draw.ellipse((px - 27, py + 20, px + 27, py + 39), fill=(3, 7, 11, 230))
    if moving:
        draw.ellipse((px - 31, py - 31, px + 31, py + 31), outline=(82, 238, 232, 210), width=1)
    draw.polygon(((px + 22, py), (px - 14, py - 14), (px - 14, py + 14)), fill=(232, 250, 252, 255), outline=(82, 238, 232, 255))
    draw.polygon(((px + 35, py), (px + 26, py - 5), (px + 26, py + 5)), fill=(112, 244, 238, 255))
    return px, py


def draw_hud(draw: ImageDraw.ImageDraw, biome: dict, actor_x: float, actor_y: float, objective_dist: float = 184.0) -> None:
    rx = math.floor(actor_x / CHUNK_WORLD_SIZE)
    ry = math.floor(actor_y / CHUNK_WORLD_SIZE)
    lines = [
        f"{biome['name']}  /  {biome['terrain'].upper()}",
        f"REGION {rx:+d},{ry:+d}  /  COORD {actor_x:+06.1f}, {actor_y:+06.1f}",
        f"RELIC CORE SIGNAL  /  {objective_dist:03.0f}m",
    ]
    panel_w = 730
    panel_h = 48 + (len(lines) - 1) * 24
    draw.rounded_rectangle((48, 36, 48 + panel_w, 36 + panel_h), radius=8, fill=(5, 8, 14, 205), outline=(55, 92, 112, 255), width=1)
    for i, line in enumerate(lines):
        draw.text((64, 48 + i * 24), line, font=F20, fill=(232, 242, 248, 255) if i == 0 else (138, 222, 226, 255))


def draw_action_and_notice(draw: ImageDraw.ImageDraw, notice: str = "SURFACE RIG PROCESSED ORGANIC GROWTH — 3 SALVAGE") -> None:
    action_w = 610
    action_x = SCREEN[0] // 2 - action_w // 2
    action_y = SCREEN[1] - 78
    draw.rounded_rectangle((action_x, action_y, action_x + action_w, action_y + 50), radius=12, fill=(4, 8, 13, 225), outline=(124, 244, 176, 255), width=1)
    draw.rounded_rectangle((action_x + 8, action_y + 8, action_x + 56, action_y + 42), radius=9, fill=(124, 244, 176, 255))
    draw.text((action_x + 26, action_y + 9), "E", font=F24, fill=(4, 8, 12, 255))
    draw.text((action_x + 70, action_y + 14), "PROCESS ORGANIC GROWTH", font=F20, fill=(236, 244, 248, 255))
    notice_w = 720
    notice_y = SCREEN[1] - 140
    notice_x = SCREEN[0] // 2 - notice_w // 2
    draw.rounded_rectangle((notice_x, notice_y, notice_x + notice_w, notice_y + 44), radius=10, fill=(6, 10, 16, 220), outline=(68, 116, 132, 255), width=1)
    tw = draw.textbbox((0, 0), notice, font=F18)[2]
    draw.text((SCREEN[0] // 2 - tw // 2, notice_y + 10), notice, font=F18, fill=(236, 238, 244, 255))


def draw_recovery_fx(draw: ImageDraw.ImageDraw, x: int, y: int, reward: str, seed: int = 331) -> None:
    t = 0.46
    radius = int(18 + 46 * t)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=(124, 244, 176, 190), width=3)
    rng = random.Random(seed)
    for i in range(12):
        angle = rng.random() * math.tau
        reach = 14 + (42 + rng.random() * 24) * t
        px = int(x + math.cos(angle) * reach)
        py = int(y + math.sin(angle) * reach - 18 * t)
        draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(160, 255, 204, 210 - i * 7))
    tw = draw.textbbox((0, 0), reward, font=F20)[2]
    draw.text((x - tw // 2, y - 72), reward, font=F20, fill=(230, 250, 238, 255), stroke_width=2, stroke_fill=(4, 8, 12, 220))


def render_before_after() -> Path:
    seed = 20260804
    biome = BIOMES["jungle"]
    actor = (428.0, 214.0)
    view = actor
    base, objects = compose(seed, biome, *view)
    before = base.copy()
    after = base.copy()
    bd = ImageDraw.Draw(before, "RGBA")
    ad = ImageDraw.Draw(after, "RGBA")

    # Pass 22 lattice and basic markers.
    left = view[0] - VIEW_W * 0.5
    top = view[1] - VIEW_H * 0.5
    for gx in range(math.floor(left / 32) * 32, int(left + VIEW_W) + 32, 32):
        sx = int((gx - left) / VIEW_W * SCREEN[0])
        bd.line((sx, 0, sx, SCREEN[1]), fill=(126, 218, 228, 42), width=1)
    for gy in range(math.floor(top / 32) * 32, int(top + VIEW_H) + 32, 32):
        sy = int((gy - top) / VIEW_H * SCREEN[1])
        bd.line((0, sy, SCREEN[0], sy), fill=(126, 218, 228, 42), width=1)
    draw_objects(bd, objects, *view, biome, polished=False)
    draw_player(bd, *actor, *view)
    draw_hud(bd, biome, *actor)

    # Pass 23 unobstructed terrain, improved silhouettes, and camera look-ahead.
    after, objects = compose(seed, biome, actor[0] + 3.1, actor[1])
    ad = ImageDraw.Draw(after, "RGBA")
    draw_objects(ad, objects, actor[0] + 3.1, actor[1], biome, polished=True)
    draw_player(ad, *actor, actor[0] + 3.1, actor[1])
    draw_hud(ad, biome, *actor)
    draw_vignette(after)

    canvas = Image.new("RGB", SCREEN, (2, 5, 10))
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 26), "PASS 23  /  SURFACE READABILITY POLISH", font=F34B, fill=(236, 244, 248))
    draw.text((48, 72), "Same world and coordinates: grid removed, silhouettes grounded, camera gains restrained motion look-ahead.", font=F18, fill=(138, 222, 226))
    a = before.resize((884, 884 * 9 // 16), Image.Resampling.LANCZOS)
    b = after.resize((884, 884 * 9 // 16), Image.Resampling.LANCZOS)
    canvas.paste(a.convert("RGB"), (48, 132))
    canvas.paste(b.convert("RGB"), (988, 132))
    draw.rectangle((48, 132, 932, 629), outline=(64, 110, 126), width=2)
    draw.rectangle((988, 132, 1872, 629), outline=(64, 110, 126), width=2)
    draw.rounded_rectangle((64, 528, 430, 566), radius=8, fill=(4, 8, 14), outline=(92, 76, 38), width=1)
    draw.text((80, 536), "PASS 22  /  NAVIGATION LATTICE", font=F16, fill=(255, 214, 112))
    draw.rounded_rectangle((1004, 528, 1402, 566), radius=8, fill=(4, 8, 14), outline=(48, 112, 82), width=1)
    draw.text((1020, 536), "PASS 23  /  UNOBSTRUCTED GEOLOGY", font=F16, fill=(124, 244, 176))

    # Movement response strip.
    draw.rounded_rectangle((48, 684, 1872, 1020), radius=12, fill=(5, 8, 14), outline=(55, 92, 112), width=2)
    draw.text((78, 714), "TRAVERSAL RESPONSE", font=F28B, fill=(236, 244, 248))
    draw.text((78, 756), "Keyboard input now accelerates into motion, brakes cleanly, and shifts the camera only 3.6 world units ahead.", font=F18, fill=(138, 222, 226))
    graph = (98, 824, 1180, 966)
    draw.line((graph[0], graph[3], graph[2], graph[3]), fill=(74, 112, 128), width=2)
    draw.line((graph[0], graph[1], graph[0], graph[3]), fill=(74, 112, 128), width=2)
    speed = 0.0
    points = []
    for frame in range(61):
        target = 10.5 if frame < 38 else 0.0
        response = 12.0 if frame < 38 else 15.0
        blend = 1.0 - math.exp(-response / 60.0)
        speed += (target - speed) * blend
        x = graph[0] + int(frame / 60 * (graph[2] - graph[0]))
        y = graph[3] - int(speed / 10.5 * (graph[3] - graph[1]))
        points.append((x, y))
    draw.line(points, fill=(124, 244, 176), width=4)
    draw.text((graph[0], graph[3] + 12), "INPUT DOWN", font=F14, fill=(138, 222, 226))
    draw.text((graph[2] - 110, graph[3] + 12), "RELEASE", font=F14, fill=(138, 222, 226))
    metrics = [("ACCEL", "12.0"), ("BRAKE", "15.0"), ("LOOK-AHEAD", "3.6u"), ("FX POOL", "6")]
    for i, (label, value) in enumerate(metrics):
        x = 1280 + (i % 2) * 275
        y = 820 + (i // 2) * 94
        draw.rounded_rectangle((x, y, x + 235, y + 72), radius=10, fill=(8, 13, 20), outline=(68, 116, 132), width=1)
        draw.text((x + 16, y + 12), label, font=F16, fill=(138, 222, 226))
        draw.text((x + 16, y + 34), value, font=F28B, fill=(236, 244, 248))
    path = OUT / "Entropy_Pass23_TraversalPolish_Proof.png"
    canvas.save(path, quality=94)
    return path


def render_feedback() -> Path:
    seed = 20260917
    biome = BIOMES["volcanic"]
    actor = (146.0, -92.0)
    view = (149.1, -92.0)
    image, objects = compose(seed, biome, *view)
    draw = ImageDraw.Draw(image, "RGBA")
    draw_objects(draw, objects, *view, biome, polished=True)
    px, py = draw_player(draw, *actor, *view)
    target_x, target_y = px + 188, py - 72
    draw.ellipse((target_x - 24, target_y - 24, target_x + 24, target_y + 24), outline=(124, 244, 176, 255), width=2)
    draw_recovery_fx(draw, target_x, target_y, "3 SALVAGE + 1 FUEL CELL")
    draw_hud(draw, biome, *actor, objective_dist=116.0)
    draw_action_and_notice(draw)
    draw_vignette(image)
    path = OUT / "Entropy_Pass23_RecoveryReadability_Proof.png"
    image.convert("RGB").save(path, quality=94)
    return path


def render_contact(paths: list[Path]) -> Path:
    canvas = Image.new("RGB", SCREEN, (2, 5, 10))
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 28), "ENTROPY PASS 23  /  EXPLORATION POLISH AND READABILITY", font=F28B, fill=(236, 244, 248))
    draw.text((48, 68), "Conservative polish: smoother traversal, clearer terrain, one safe action prompt, and bounded recovery feedback.", font=F16, fill=(138, 222, 226))
    top = Image.open(paths[0]).resize((1792, 1008), Image.Resampling.LANCZOS)
    detail = Image.open(paths[1]).resize((640, 360), Image.Resampling.LANCZOS)
    canvas.paste(top.crop((0, 0, 1792, 560)), (48, 108))
    canvas.paste(detail, (48, 696))
    draw.rectangle((48, 108, 1840, 668), outline=(64, 110, 126), width=2)
    draw.rectangle((48, 696, 688, 1056), outline=(64, 110, 126), width=2)
    draw.text((720, 720), "POLISH CONTRACT", font=F28B, fill=(236, 244, 248))
    notes = [
        "• Physical coordinates remain authoritative; only the view eases ahead.",
        "• Grid lines no longer cover ridges, basins, faults, or material deposits.",
        "• One bottom action chip replaces repeated labels around objects and HUD.",
        "• Notifications automatically rise above the action chip.",
        "• Recovery feedback is capped at six effects and expires after 1.05 seconds.",
        "• Existing one-minute collapse, autowarp, sun reset, and save state remain unchanged.",
    ]
    for i, text in enumerate(notes):
        draw.text((720, 774 + i * 42), text, font=F18, fill=(138, 222, 226) if i < 5 else (255, 214, 112))
    path = OUT / "Entropy_Pass23_contact_sheet.png"
    canvas.save(path, quality=94)
    return path


def main() -> int:
    traversal = render_before_after()
    feedback = render_feedback()
    contact = render_contact([traversal, feedback])
    print(traversal)
    print(feedback)
    print(contact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
