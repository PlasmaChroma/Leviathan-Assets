#!/usr/bin/env python3

from PIL import Image, ImageFilter, ImageChops
import os

# --------------------------------------------------
# Files
# --------------------------------------------------
INPUT_IMAGE = "Underlays.png"
OUT_LEFT = "cyan_underlay.png"
OUT_RIGHT = "purple_underlay.png"

# --------------------------------------------------
# Detection settings
# Used only for locating the visible object
# --------------------------------------------------
DETECT_CUTOFF = 28   # higher = tighter detection
PADDING = 80         # extra crop area around detected object

# --------------------------------------------------
# Alpha settings
# Used for the final output appearance
# --------------------------------------------------
BLACK_CUTOFF = 8        # below this brightness is considered dark background
SOFT_RANGE = 75         # alpha ramps up across this brightness range
DARK_FLOOR_ALPHA = 24   # preserves some dark area at low alpha for contrast
BLUR_ALPHA = 1.0        # softens alpha slightly

# --------------------------------------------------
# Outer envelope settings
# These force alpha to 0 near/beyond the border
# --------------------------------------------------
EDGE_INSET = 8       # distance in from crop edge before fade starts
EDGE_FEATHER = 22    # width of fade band to full transparency

# --------------------------------------------------
# Output scaling
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
    This is used only to detect the object bounds.
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
    Build alpha from brightness but preserve some low-alpha dark surround,
    so the underlay keeps contrast when composited under the orb.
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


def make_radial_envelope(size, inset=8, feather=22):
    """
    Create an elliptical alpha envelope:
    - full alpha in the interior
    - fades toward 0 near the border
    - 0 outside the outer boundary
    """
    w, h = size
    mask = Image.new("L", (w, h), 0)
    px = mask.load()

    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0

    rx_outer = max(1.0, (w / 2.0) - inset)
    ry_outer = max(1.0, (h / 2.0) - inset)

    rx_inner = max(1.0, rx_outer - feather)
    ry_inner = max(1.0, ry_outer - feather)

    for y in range(h):
        for x in range(w):
            dx = x - cx
            dy = y - cy

            outer_norm = (dx * dx) / (rx_outer * rx_outer) + (dy * dy) / (ry_outer * ry_outer)
            inner_norm = (dx * dx) / (rx_inner * rx_inner) + (dy * dy) / (ry_inner * ry_inner)

            if inner_norm <= 1.0:
                a = 255
            elif outer_norm >= 1.0:
                a = 0
            else:
                # Linear fade between inner and outer ellipse
                t = (outer_norm - 1.0) / (outer_norm - inner_norm)
                t = clamp(t, 0.0, 1.0)
                a = int(255 * t)

            px[x, y] = a

    return mask


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

    # Apply elliptical envelope so alpha reaches 0 at the outside border
    envelope = make_radial_envelope(
        out.size,
        inset=EDGE_INSET,
        feather=EDGE_FEATHER
    )

    r, g, b, a = out.split()
    a = ImageChops.multiply(a, envelope)
    out.putalpha(a)

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

    # Split into left and right halves
    left_half = img.crop((0, 0, mid, h))
    right_half = img.crop((mid, 0, w, h))

    process_half(left_half, OUT_LEFT)
    process_half(right_half, OUT_RIGHT)


if __name__ == "__main__":
    main()