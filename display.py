#!/usr/bin/env python3
"""
Shared display helpers to render centered text on the ST7735 LCD in the same
style as hello-on-center.py (white background, black text, best-fit font).

This module is intentionally dependency-light: callers pass the initialized
st7735 display instance and its width/height. The helpers only use Pillow.
"""
from __future__ import annotations
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont


def choose_font(message: str, size: Tuple[int, int]) -> ImageFont.ImageFont:
    """Binary-search a font size that best fits inside the display area.
    Tries DejaVuSans-Bold first, then falls back to default.
    """
    width, height = size
    try:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        import os
        font_path = next((p for p in font_paths if os.path.exists(p)), None)
        if not font_path:
            return ImageFont.load_default()
        draw = ImageDraw.Draw(Image.new('RGB', (width, height)))
        lo, hi = 6, height
        best = ImageFont.truetype(font_path, 12)
        while lo <= hi:
            mid = (lo + hi) // 2
            f = ImageFont.truetype(font_path, mid)
            bbox = draw.textbbox((0, 0), message, font=f)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= width - 8 and th <= height - 8:
                best = f
                lo = mid + 1
            else:
                hi = mid - 1
        return best
    except Exception:
        return ImageFont.load_default()


def render_centered_text_hello_style(disp, size: Tuple[int, int], message: str):
    """Render text like hello-on-center:
    - white background
    - black text
    - centered
    - best-fit font
    """
    width, height = size
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = choose_font(message, (width, height))
    bbox = draw.textbbox((0, 0), message, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max(0, (width - tw) // 2)
    y = max(0, (height - th) // 2)
    draw.text((x, y), message, font=font, fill=(0, 0, 0))
    disp.display(img)


def render_centered_text_server_style(disp, size: Tuple[int, int], message: str):
    """Render text like the previous Flask server style (yellow on black).
    Kept in case some callers prefer the old appearance.
    """
    width, height = size
    img = Image.new('RGB', (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = choose_font(message, (width, height))
    bbox = draw.textbbox((0, 0), message, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max(0, (width - tw) // 2)
    y = max(0, (height - th) // 2)
    # optional small black rectangle padding is redundant on black background
    draw.text((x, y), message, font=font, fill=(255, 255, 0))
    disp.display(img)
