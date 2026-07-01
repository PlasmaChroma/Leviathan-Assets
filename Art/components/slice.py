#!/usr/bin/env python3

from PIL import Image, ImageFilter
import os

# Input image path
INPUT_IMAGE = "Orbs.png"

# Output files
OUT_LEFT = "cyan_orb.png"
OUT_RIGHT = "purple_orb.png"

# Tunables
PADDING = 24             # pixels around final crop
BLACK_CUTOFF = 10        # below this brightness is treated as black/transparent
SOFT_RANGE = 70          # alpha ramp range above BLACK_CUTOFF
BLUR_ALPHA = 1.2         # soften transparency edges slightly
DOWNSAMPLE_FACTOR = 4    # 2 = half resolution, 1 = no resizing


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def make_transparent_crop(img, out_path):
    """
    Convert near-black background to transparency,
    preserve glow, crop to content bounds, optionally downsample,
    and save as PNG.
    """
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    alpha_img = Image.new("L", (w, h), 0)
    alpha_px = alpha_img.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]

            # Use max channel so colored glow survives.
            brightness = max(r, g, b)

            if brightness <= BLACK_CUTOFF:
                alpha = 0
            else:
                alpha = int(
                    255 * clamp(
                        (brightness - BLACK_CUTOFF) / SOFT_RANGE,
                        0.0,
                        1.0
                    )
                )

            alpha_px[x, y] = alpha

    # Feather alpha boundary slightly.
    if BLUR_ALPHA > 0:
        alpha_img = alpha_img.filter(
            ImageFilter.GaussianBlur(radius=BLUR_ALPHA)
        )

    out = img.copy()
    out.putalpha(alpha_img)

    # Crop to non-transparent bounds.
    bbox = alpha_img.getbbox()
    if bbox is None:
        print(f"No visible content found for {out_path}")
        return

    left, top, right, bottom = bbox

    left = max(0, left - PADDING)
    top = max(0, top - PADDING)
    right = min(w, right + PADDING)
    bottom = min(h, bottom + PADDING)

    out = out.crop((left, top, right, bottom))

    # Downsample after alpha extraction and cropping.
    if DOWNSAMPLE_FACTOR > 1:
        new_w = max(1, out.size[0] // DOWNSAMPLE_FACTOR)
        new_h = max(1, out.size[1] // DOWNSAMPLE_FACTOR)

        out = out.resize(
            (new_w, new_h),
            Image.Resampling.LANCZOS
        )

    out.save(out_path)
    print(f"Saved {out_path} ({out.size[0]}x{out.size[1]})")


def main():
    if not os.path.exists(INPUT_IMAGE):
        raise FileNotFoundError(f"Input image not found: {INPUT_IMAGE}")

    img = Image.open(INPUT_IMAGE).convert("RGBA")
    w, h = img.size

    # Split source image into left and right halves.
    mid = w // 2

    left_half = img.crop((0, 0, mid, h))
    right_half = img.crop((mid, 0, w, h))

    make_transparent_crop(left_half, OUT_LEFT)
    make_transparent_crop(right_half, OUT_RIGHT)


if __name__ == "__main__":
    main()