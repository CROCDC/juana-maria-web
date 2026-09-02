#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "media-web" / "photos"
OUT = ROOT / "public" / "static" / "img"
# The app reads this from inside the package, not from the served asset tree
# (see app/factory.py:_load_image_manifest).
MANIFEST = ROOT / "app" / "content" / "image_manifest.json"

WIDTHS = [1920, 1280, 960, 640, 420]
WEBP_QUALITY = 80
JPEG_QUALITY = 82
JPEG_FALLBACK_WIDTH = 1280

WATERMARK_CROP = 0.075
WATERMARKED = {
    "moored/profile-with-name",
    "moored/at-club-with-sister",
    "interior/galley-and-nav",
    "details/builders-plaque-full",
    "details/builders-plaque-closeup",
}

# Family photos not yet cleared for publication: they ship stamped so nobody mistakes
# them for approved artwork. The two `hero/` shots left this set on 13/08/2026, when the
# owner picked them by name for the cover and the gallery.
PEOPLE = {
    "sailing/two-balleneras-golden-hour",
    "sailing/two-balleneras-bsas-skyline",
    "on-deck/foredeck-stormy-sky",
    "on-deck/foredeck-detail",
    "moored/two-boats-night",
}

WM_FONT = ROOT / "scripts" / "assets" / "CormorantGaramond-SemiBold.ttf"
WM_LINES = ["JUANA MARÍA", "FOTO FAMILIAR"]
WM_ANGLE = 30
WM_FONT_FRAC = 0.050
WM_GAP_X = 1.9
WM_GAP_Y = 3.4
WM_TRACKING = 0.16
WM_FILL = (249, 244, 233)
WM_ALPHA = 125
WM_STROKE = (20, 14, 8)
WM_STROKE_ALPHA = 95


def watermark(img: Image.Image) -> Image.Image:
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


IMAGES = {
    "hero/under-full-sail": "hero/under-full-sail",
    "hero/sailing-returning-from-colonia": "hero/heeling-blue",
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
    "on-deck/cockpit": "on-deck/cockpit",
    "interior/galley-and-nav": "interior/galley-and-nav",
    "interior/cabin": "interior/cabin",
    "interior/books-aboard": "interior/books-aboard",
    "details/builders-plaque-full": "details/plaque-full",
    "details/builders-plaque-closeup": "details/plaque-closeup",
    "details/bronze-fitting-sunset": "details/bronze-fitting",
    "details/lamp-and-barometer": "details/lamp-and-barometer",
    "details/bronze-vent": "details/bronze-vent",
    "heritage/sail-plan-campos": "heritage/sail-plan-campos",
}


def variant_widths(full_w: int) -> list[int]:
    """The webp widths to emit for a source `full_w` pixels wide, largest first.

    A source narrower than the widest standard step also gets a variant at its own
    width: several photos the owner sent are ~1100 px wide, and rounding those down to
    the next step (960) would throw away real pixels on a full-bleed header.
    """
    widths = [w for w in WIDTHS if w <= full_w]
    if full_w not in widths and full_w < max(WIDTHS):
        widths = [full_w, *widths]
    return widths or [full_w]


def process(src_rel: str, out_key: str) -> dict[str, object]:
    src_path = SRC / f"{src_rel}.jpg"
    img = Image.open(src_path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    if src_rel in WATERMARKED:
        w, h = img.size
        crop_h = int(h * (1 - WATERMARK_CROP))
        img = img.crop((0, 0, w, crop_h))

    if src_rel in PEOPLE:
        img = watermark(img)

    out_dir = OUT / Path(out_key).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    name = Path(out_key).name
    full_w, full_h = img.size
    widths = variant_widths(full_w)

    for target in widths:
        ratio = target / full_w
        resized = img.resize((target, round(full_h * ratio)), Image.LANCZOS)
        resized.save(
            out_dir / f"{name}-{target}.webp",
            "WEBP",
            quality=WEBP_QUALITY,
            method=6,
        )

    fb_w = min(JPEG_FALLBACK_WIDTH, full_w)
    fb = img.resize((fb_w, round(full_h * fb_w / full_w)), Image.LANCZOS)
    fb.save(out_dir / f"{name}-fallback.jpg", "JPEG", quality=JPEG_QUALITY, progressive=True, optimize=True)

    return {"w": full_w, "h": full_h, "widths": widths}


def main() -> None:
    manifest: dict[str, dict[str, object]] = {}
    for src_rel, out_key in IMAGES.items():
        dims = process(src_rel, out_key)
        manifest[out_key] = dims
        print(f"  {out_key:32s} {dims['w']}x{dims['h']}")
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {len(manifest)} images -> {OUT}")


if __name__ == "__main__":
    main()
