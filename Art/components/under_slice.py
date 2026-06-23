#!/usr/bin/env python3

from PIL import Image, ImageFilter
import os

# --------------------------------------------------
# Files
# --------------------------------------------------
INPUT_IMAGE = "Underlays.png"
OUT_LEFT = "cyan_underlay.png"
OUT_RIGHT = "purple_underlay.png"

# --------------------------------------------------
# Detection settings (used only to find object bounds)
# --------------------------------------------------
DETECT_CUTOFF = 28      # higher = tighter detection
PADDING = 60            # extra space around detected object

# --------------------------------------------------
# Alpha settings (used for the final output image)
# --------------------------------------------------
BLACK_CUTOFF = 8        # below this brightness is "dark background"
SOFT_RANGE = 75         # how fast alpha ramps up above BLACK_CUTOFF
DARK_FLOOR_ALPHA = 28   # preserves some dark surround for contrast
BLUR_ALPHA = 1.0        # softens edge transitions slightly

# --------------------------------------------------
# Output scale
# 1 = full size
# 2 = half width/height
# 4 = quarter width/height
# --------------------------------------------------
DOWNSAMPLE_FACTOR = 4


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def find_content_bbox(img, cutoff):
    """
    Find bounding box of all pixels above a brightness cutoff.
    Uses a hard detection mask only for locating the object.
    """
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    mask = Image.new("L", (w, h), 0)
    mask_px = mask.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            brightness = max(r, g, b)
            mask_px[x, y] = 255 if brightness > cutoff else 0

    return mask.getbbox()


def make_alpha_preserving_dark(img):
    """
    Build alpha from brightness but preserve a small amount of dark background
    as low alpha, so the asset retains some contrast when composited.
    """
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    alpha_img = Image.new("L", (w, h), 0)
    alpha_px = alpha_img.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            brightness = max(r, g, b)

            if brightness <= BLACK_CUTOFF:
                alpha = DARK_FLOOR_ALPHA
            else:
                t = clamp((brightness - BLACK_CUTOFF) / SOFT_RANGE, 0.0, 1.0)
                alpha = int(DARK_FLOOR_ALPHA + t * (255 - DARK_FLOOR_ALPHA))

            alpha_px[x, y] = alpha

    if BLUR_ALPHA > 0:
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=BLUR_ALPHA))

    out = img.copy()
    out.putalpha(alpha_img)
    return out


def crop_with_padding(img, bbox, padding):
    w, h = img.size
    left, top, right, bottom = bbox

    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(w, right + padding)
    bottom = min(h, bottom + padding)

    return img.crop((left, top, right, bottom))


def process_half(img, out_path):
    bbox = find_content_bbox(img, DETECT_CUTOFF)
    if bbox is None:
        print(f"No visible content found for {out_path}")
        return

    cropped = crop_with_padding(img, bbox, PADDING)
    out = make_alpha_preserving_dark(cropped)

    if DOWNSAMPLE_FACTOR > 1:
        new_w = max(1, out.size[0] // DOWNSAMPLE_FACTOR)
        new_h = max(1, out.size[1] // DOWNSAMPLE_FACTOR)
        out = out.resize((new_w, new_h), Image.Resampling.LANCZOS)

    out.save(out_path)
    print(f"Saved {out_path} ({out.size[0]}x{out.size[1]})")


def main():
    if not os.path.exists(INPUT_IMAGE):
        raise FileNotFoundError(f"Input image not found: {INPUT_IMAGE}")

    img = Image.open(INPUT_IMAGE).convert("RGBA")
    w, h = img.size
    mid = w // 2

    # Left/cyan side
    left_half = img.crop((0, 0, mid, h))

    # Right/purple side
    right_half = img.crop((mid, 0, w, h))

    process_half(left_half, OUT_LEFT)
    process_half(right_half, OUT_RIGHT)


if __name__ == "__main__":
    main()