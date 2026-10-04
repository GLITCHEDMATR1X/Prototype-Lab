from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "verification" / "screenshots"
OUT = ROOT / "itch_media"
SHOTS = OUT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


SELECTIONS = [
    ("01_One_Minute_Run.png", "Entropy_Pass21_OneMinuteStart_Proof.png", "ONE MINUTE PER SYSTEM"),
    ("02_Surface_Recovery.png", "Entropy_Pass23_RecoveryReadability_Proof.png", "PROCESS THE WORLD"),
    ("03_Solar_Erosion.png", "Entropy_Pass21_SolarErosion_Proof.png", "PLANETS DETERIORATE"),
    ("04_Critical_Collapse.png", "Entropy_Pass21_CriticalErosion_Proof.png", "ESCAPE THE COLLAPSE"),
    ("05_Ship_Fabricator.png", "Entropy_Pass18_1_RelicFabricator_Proof.png", "UPGRADE THE EXPEDITION"),
]

for target_name, source_name, _caption in SELECTIONS:
    source = SRC / source_name
    if not source.is_file():
        raise FileNotFoundError(source)
    Image.open(source).convert("RGB").save(SHOTS / target_name, optimize=True)

# 630x500 itch cover derived from the actual one-minute briefing proof.
base = Image.open(SRC / "Entropy_Pass21_OneMinuteStart_Proof.png").convert("RGB")
target_ratio = 630 / 500
w, h = base.size
crop_w = min(w, int(round(h * target_ratio)))
left = max(0, (w - crop_w) // 2)
cover = base.crop((left, 0, left + crop_w, h)).resize((630, 500), Image.Resampling.LANCZOS)
cover = ImageEnhance.Contrast(cover).enhance(1.08)
overlay = Image.new("RGBA", cover.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay, "RGBA")
draw.rectangle((0, 0, 630, 126), fill=(1, 4, 9, 214))
draw.rectangle((0, 405, 630, 500), fill=(1, 4, 9, 220))
draw.line((34, 126, 596, 126), fill=(102, 231, 235, 190), width=2)
draw.line((34, 405, 596, 405), fill=(102, 231, 235, 140), width=1)
cover = Image.alpha_composite(cover.convert("RGBA"), overlay)
draw = ImageDraw.Draw(cover)
main_font = font(62, True)
sub_font = font(18, True)
small_font = font(15)
draw.text((315, 28), "ENTROPY", font=main_font, fill=(238, 247, 250), anchor="ma")
draw.text((315, 99), "ONE MINUTE  /  ONE WORLD  /  KEEP MOVING", font=sub_font, fill=(108, 239, 235), anchor="ma")
draw.text((315, 438), "SCI-FI SURVIVAL-EXPLORATION PROTOTYPE", font=sub_font, fill=(226, 238, 242), anchor="ma")
draw.text((315, 470), "GLITCHED MATRIX", font=small_font, fill=(150, 177, 190), anchor="ma")
cover.convert("RGB").save(OUT / "Entropy_Cover_630x500.png", optimize=True)

# 1920x1080 visual audit/contact sheet.
sheet = Image.new("RGB", (1920, 1080), (2, 6, 11))
draw = ImageDraw.Draw(sheet)
draw.text((54, 40), "ENTROPY  /  RELEASE CANDIDATE 1", font=font(38, True), fill=(238, 247, 250))
draw.text((56, 94), "FINAL ITCH PAGE MEDIA SELECTION", font=font(20, True), fill=(103, 234, 231))

slots = [
    (54, 150, 884, 470),
    (982, 150, 884, 470),
    (54, 674, 558, 314),
    (681, 674, 558, 314),
    (1308, 674, 558, 314),
]
for (target_name, _source_name, caption), (x, y, tw, th) in zip(SELECTIONS, slots):
    img = Image.open(SHOTS / target_name).convert("RGB")
    scale = min(tw / img.width, th / img.height)
    rw, rh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    thumb = img.resize((rw, rh), Image.Resampling.LANCZOS)
    px, py = x + (tw - rw) // 2, y + (th - rh) // 2
    sheet.paste(thumb, (px, py))
    draw.rectangle((x, y, x + tw, y + th), outline=(58, 112, 130), width=2)
    label_w = min(tw - 20, 360)
    draw.rounded_rectangle((x + 14, y + th - 48, x + 14 + label_w, y + th - 12), radius=6, fill=(3, 9, 15), outline=(70, 179, 189), width=1)
    draw.text((x + 28, y + th - 41), caption, font=font(17, True), fill=(219, 242, 244))

sheet.save(OUT / "Entropy_RC1_contact_sheet.png", optimize=True)

captions = """ENTROPY ITCH SCREENSHOT CAPTIONS\n================================\n\n01 — Every system begins with a one-minute collapse clock and one clear world objective.\n02 — Explore seamless procedural terrain and process world objects into Salvage and Fuel Cells.\n03 — Planets shed tiny sunward pixels as their star destabilizes.\n04 — Collapse pressure intensifies into supernova and black-hole deterioration.\n05 — Spend Relic Cores or Salvage on the ship's existing upgrade tracks.\n"""
(OUT / "SCREENSHOT_CAPTIONS.txt").write_text(captions, encoding="utf-8")
print(OUT / "Entropy_Cover_630x500.png")
print(OUT / "Entropy_RC1_contact_sheet.png")
