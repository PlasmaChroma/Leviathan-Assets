#!/usr/bin/env python3
"""
cut-switch.py

Pillow-only / NumPy-only background remover for the generated sci-fi switch image.

Usage:
    python3 cut-switch.py input.png output.png

Or edit INPUT_FILE / OUTPUT_FILE below and run:
    python3 cut-switch.py
"""

from pathlib import Path
from collections import deque

import numpy as np
from PIL import Image, ImageFilter


INPUT_FILE = "futuristic_sci_fi_metallic_panel.png"
OUTPUT_FILE = "switch-cutout.png"

# Tuneables
PADDING = 16

# Background is fake checkerboard: bright, low-saturation whites/grays.
BG_MIN_BRIGHTNESS = 205
BG_MAX_CHANNEL_SPREAD = 28

# Helps remove tiny isolated specks.
ALPHA_THRESHOLD = 20


def is_background_pixel(rgb):
    """
    Identify bright neutral checkerboard pixels.
    Works well for white / light gray generated transparency backgrounds.
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maxc = np.maximum.reduce([r, g, b])
    minc = np.minimum.reduce([r, g, b])
    spread = maxc - minc

    bright = maxc >= BG_MIN_BRIGHTNESS
    neutral = spread <= BG_MAX_CHANNEL_SPREAD

    return bright & neutral


def flood_fill_background(bg_candidate):
    """
    Keep only background connected to image edges.
    This avoids punching holes through bright metallic highlights inside the switch.
    """
    h, w = bg_candidate.shape
    visited = np.zeros((h, w), dtype=bool)
    q = deque()

    # Seed flood fill from all edge pixels that look like background.
    for x in range(w):
        if bg_candidate[0, x]:
            q.append((0, x))
        if bg_candidate[h - 1, x]:
            q.append((h - 1, x))

    for y in range(h):
        if bg_candidate[y, 0]:
            q.append((y, 0))
        if bg_candidate[y, w - 1]:
            q.append((y, w - 1))

    while q:
        y, x = q.popleft()

        if visited[y, x] or not bg_candidate[y, x]:
            continue

        visited[y, x] = True

        if y > 0:
            q.append((y - 1, x))
        if y < h - 1:
            q.append((y + 1, x))
        if x > 0:
            q.append((y, x - 1))
        if x < w - 1:
            q.append((y, x + 1))

    return visited


def main():
    import sys

    input_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path(INPUT_FILE)
    output_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path(OUTPUT_FILE)

    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)

    rgb = arr[..., :3].astype(np.uint8)

    bg_candidate = is_background_pixel(rgb)
    true_bg = flood_fill_background(bg_candidate)

    # Foreground is everything not connected to the outer background.
    alpha = np.where(true_bg, 0, 255).astype(np.uint8)

    # Convert alpha to image so we can use Pillow filters for cleanup.
    alpha_img = Image.fromarray(alpha, mode="L")

    # Close tiny gaps around edges.
    alpha_img = alpha_img.filter(ImageFilter.MaxFilter(5))
    alpha_img = alpha_img.filter(ImageFilter.MinFilter(5))

    # Slight feather for nicer anti-aliased edge.
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(0.8))

    alpha = np.array(alpha_img)

    # Apply alpha.
    arr[..., 3] = alpha

    # Crop to nontransparent bounds.
    ys, xs = np.where(alpha > ALPHA_THRESHOLD)

    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError("No switch detected. Try lowering BG_MIN_BRIGHTNESS.")

    x0 = max(xs.min() - PADDING, 0)
    y0 = max(ys.min() - PADDING, 0)
    x1 = min(xs.max() + PADDING + 1, arr.shape[1])
    y1 = min(ys.max() + PADDING + 1, arr.shape[0])

    cropped = arr[y0:y1, x0:x1]

    Image.fromarray(cropped, mode="RGBA").save(output_path)

    print(f"Saved: {output_path}")
    print(f"Crop: x={x0}, y={y0}, w={x1 - x0}, h={y1 - y0}")


if __name__ == "__main__":
    main()