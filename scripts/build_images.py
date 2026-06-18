#!/usr/bin/env python3
"""Build responsive, web-optimized images for the Juana María site.

Reads the curated masters in ``media-web/photos/`` and writes, per image, a
ladder of WebP widths plus a single JPEG fallback into ``app/static/img/``.
Broker (FINARA) shots carry a small corner watermark; those are cropped along
the bottom edge before resizing. A JSON manifest with intrinsic dimensions is
written so templates can set width/height and avoid layout shift.

Shots that show identifiable people are private family photos, not stock: those
get a crossed, tiled "JUANA MARÍA / FOTO FAMILIAR" watermark baked in (at master
resolution, so it scales down cleanly into every responsive width) to discourage
reuse. Only the master in ``media-web/photos/`` stays clean.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "media-web" / "photos"
OUT = ROOT / "app" / "static" / "img"

# Responsive widths (px). Sources are capped at 2560 long edge already.
WIDTHS = [1920, 1280, 960, 640, 420]
WEBP_QUALITY = 80
JPEG_QUALITY = 82
JPEG_FALLBACK_WIDTH = 1280

# Bottom strip (fraction of height) to crop off broker shots to drop the
# small FINARA corner watermark.
WATERMARK_CROP = 0.075
WATERMARKED = {
    "moored/profile-with-name",
    "moored/at-club-with-sister",
    "interior/galley-and-nav",
    "details/builders-plaque-full",
    "details/builders-plaque-closeup",
}

# Masters that show identifiable people (crew/guests). These are private family
# photos, so they get a visible "FOTO FAMILIAR" watermark to discourage reuse.
# Curated by hand: there are only ~20 masters, so a fixed set is more reliable
# than a person detector and adds no extra dependency. Aerials/distant shots
# with only a tiny helmsman are intentionally left out (person not identifiable).
PEOPLE = {
    "hero/under-full-sail",
    "hero/sailing-returning-from-colonia",
    "sailing/two-balleneras-golden-hour",
    "sailing/two-balleneras-bsas-skyline",
    "on-deck/foredeck-stormy-sky",
    "on-deck/foredeck-detail",
    "moored/two-boats-night",
}

# Crossed, tiled watermark applied to PEOPLE shots. Tuned to read on both bright
# sky and dark areas: warm "sail" off-white fill over a faint dark stroke.
WM_FONT = ROOT / "scripts" / "assets" / "CormorantGaramond-SemiBold.ttf"
WM_LINES = ["JUANA MARÍA", "FOTO FAMILIAR"]
WM_ANGLE = 30  # degrees; drawn at +/- this to form the "cruzada" weave
WM_FONT_FRAC = 0.050  # font size as a fraction of image width
WM_GAP_X = 1.9  # horizontal tile spacing, in multiples of the widest line
WM_GAP_Y = 3.4  # vertical tile spacing, in multiples of line height
WM_TRACKING = 0.16  # extra letter-spacing, in multiples of font size
WM_FILL = (249, 244, 233)  # --sail
WM_ALPHA = 125
WM_STROKE = (20, 14, 8)  # near --abyss
WM_STROKE_ALPHA = 95


def watermark(img: Image.Image) -> Image.Image:
    """Bake a crossed, tiled "JUANA MARÍA / FOTO FAMILIAR" mark into ``img``."""
    w, h = img.size
    fs = max(16, int(w * WM_FONT_FRAC))
    font = ImageFont.truetype(str(WM_FONT), fs)
    stroke_w = max(1, int(fs * 0.016))

    def line_width(draw: ImageDraw.ImageDraw, text: str) -> float:
        total = 0.0
        for ch in text:
            box = draw.textbbox((0, 0), ch, font=font)
            total += (box[2] - box[0]) + fs * WM_TRACKING
        return total

    def diagonal_layer(angle: float) -> Image.Image:
        # Draw on an oversized square so rotation never exposes bare corners.
        side = int(math.hypot(w, h)) + fs * 5
        layer = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        ref = draw.textbbox((0, 0), WM_LINES[0], font=font)
        step_y = int((ref[3] - ref[1]) * WM_GAP_Y)
        col_w = max(line_width(draw, t) for t in WM_LINES)
        step_x = int(col_w * WM_GAP_X)
        y, row = 0, 0
        while y < side + step_y:
            text = WM_LINES[row % len(WM_LINES)]
            # Brick-offset every other row and center shorter lines in the column.
            x = -step_x + (row % 2) * (step_x // 2) + (col_w - line_width(draw, text)) / 2
            while x < side + step_x:
                cx = x
                for ch in text:
                    draw.text(
                        (cx, y), ch, font=font,
                        fill=WM_FILL + (WM_ALPHA,),
                        stroke_width=stroke_w, stroke_fill=WM_STROKE + (WM_STROKE_ALPHA,),
                    )
                    box = draw.textbbox((0, 0), ch, font=font)
                    cx += (box[2] - box[0]) + fs * WM_TRACKING
                x += step_x
            y += step_y
            row += 1
        layer = layer.rotate(angle, resample=Image.BICUBIC, center=(side // 2, side // 2))
        left, top = (side - w) // 2, (side - h) // 2
        return layer.crop((left, top, left + w, top + h))

    base = img.convert("RGBA")
    base.alpha_composite(diagonal_layer(WM_ANGLE))
    base.alpha_composite(diagonal_layer(-WM_ANGLE))
    return base.convert("RGB")

# Curated set -> output key. Output key becomes app/static/img/<key>.*
IMAGES = {
    "hero/under-full-sail": "hero/under-full-sail",
    "hero/sailing-returning-from-colonia": "hero/returning-from-colonia",
    "sailing/two-balleneras-golden-hour": "sailing/golden-hour",
    "sailing/two-balleneras-bsas-skyline": "sailing/bsas-skyline",
    "aerial/overhead-01": "aerial/overhead-01",
    "aerial/overhead-02": "aerial/overhead-02",
    "aerial/overhead-wing-on-wing": "aerial/wing-on-wing",
    "aerial/sailing-away": "aerial/sailing-away",
    "moored/profile-with-name": "moored/profile-with-name",
    "moored/at-club-with-sister": "moored/at-club-with-sister",
    "moored/night-profile": "moored/night-profile",
    "moored/two-boats-night": "moored/two-boats-night",
    "on-deck/deck-view-sunrise": "on-deck/deck-sunrise",
    "on-deck/foredeck-stormy-sky": "on-deck/foredeck-stormy",
    "on-deck/foredeck-detail": "on-deck/foredeck-detail",
    "interior/galley-and-nav": "interior/galley-and-nav",
    "details/builders-plaque-full": "details/plaque-full",
    "details/builders-plaque-closeup": "details/plaque-closeup",
    "details/bronze-fitting-sunset": "details/bronze-fitting",
    "heritage/sister-boat-teseo": "heritage/teseo",
}


def process(src_rel: str, out_key: str) -> dict[str, int]:
    src_path = SRC / f"{src_rel}.jpg"
    img = Image.open(src_path)
    img = ImageOps.exif_transpose(img)  # honor camera orientation
    img = img.convert("RGB")

    if src_rel in WATERMARKED:
        w, h = img.size
        crop_h = int(h * (1 - WATERMARK_CROP))
        img = img.crop((0, 0, w, crop_h))

    # Bake the family-photo watermark at master resolution so it downscales
    # crisply into every responsive width below.
    if src_rel in PEOPLE:
        img = watermark(img)

    out_dir = OUT / Path(out_key).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    name = Path(out_key).name
    full_w, full_h = img.size

    for target in WIDTHS:
        if target > full_w:
            continue
        ratio = target / full_w
        resized = img.resize((target, round(full_h * ratio)), Image.LANCZOS)
        resized.save(
            out_dir / f"{name}-{target}.webp",
            "WEBP",
            quality=WEBP_QUALITY,
            method=6,
        )

    # One JPEG fallback for the rare non-WebP client.
    fb_w = min(JPEG_FALLBACK_WIDTH, full_w)
    fb = img.resize((fb_w, round(full_h * fb_w / full_w)), Image.LANCZOS)
    fb.save(out_dir / f"{name}-fallback.jpg", "JPEG", quality=JPEG_QUALITY, progressive=True, optimize=True)

    return {"w": full_w, "h": full_h}


def main() -> None:
    manifest: dict[str, dict[str, int]] = {}
    for src_rel, out_key in IMAGES.items():
        dims = process(src_rel, out_key)
        manifest[out_key] = dims
        print(f"  {out_key:32s} {dims['w']}x{dims['h']}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {len(manifest)} images -> {OUT}")


if __name__ == "__main__":
    main()
