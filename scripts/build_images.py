#!/usr/bin/env python3
"""Build responsive, web-optimized images for the Juana María site.

Reads the curated masters in ``media-web/photos/`` and writes, per image, a
ladder of WebP widths plus a single JPEG fallback into ``app/static/img/``.
Broker (FINARA) shots carry a small corner watermark; those are cropped along
the bottom edge before resizing. A JSON manifest with intrinsic dimensions is
written so templates can set width/height and avoid layout shift.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageOps

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
