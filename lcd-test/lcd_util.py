#!/usr/bin/env python3
"""
Utility helpers to use the vendor Waveshare 1.44" LCD Python driver when available.
Falls back to signaling that vendor is not available so callers can use
other drivers (e.g., st7735 pip package).

This module does not import heavy dependencies unless used.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

REPO_DIR = Path(__file__).resolve().parent
VENDOR_PY_DIR = REPO_DIR / '1.44inch-LCD-HAT-Code' / 'RaspberryPi' / 'python'


def _ensure_vendor_on_path() -> bool:
    """Add vendor python dir to sys.path if exists. Return True if present."""
    if VENDOR_PY_DIR.is_dir():
        p = str(VENDOR_PY_DIR)
        if p not in sys.path:
            sys.path.insert(0, p)
        return True
    return False


def vendor_available() -> bool:
    """Quick check if vendor driver can be imported."""
    if not _ensure_vendor_on_path():
        return False
    try:
        import LCD_1in44  # noqa: F401
        import config     # noqa: F401
        return True
    except Exception:
        return False


class VendorLCD:
    """Thin wrapper around the vendor LCD class with convenience methods."""

    def __init__(self):
        if not _ensure_vendor_on_path():
            raise RuntimeError("Vendor directory not found: {}".format(VENDOR_PY_DIR))
        # Lazy imports
        import LCD_1in44  # type: ignore
        self._mod = LCD_1in44
        self.disp = LCD_1in44.LCD()
        self._inited = False

    def begin(self, scan_dir: Optional[int] = None):
        if self._inited:
            return
        scan = scan_dir if scan_dir is not None else self._mod.SCAN_DIR_DFT
        self.disp.LCD_Init(scan)
        self._inited = True

    @property
    def size(self) -> Tuple[int, int]:
        return (self.disp.width, self.disp.height)

    def clear(self, rgb=(0, 0, 0)):
        """Clear screen. If rgb!=black, fill using PIL image."""
        from PIL import Image
        if not self._inited:
            self.begin()
        if rgb == (0, 0, 0):
            # Fast vendor clear
            self.disp.LCD_Clear()
        else:
            w, h = self.size
            img = Image.new('RGB', (w, h), rgb)
            self.disp.LCD_ShowImage(img, 0, 0)

    def show(self, image):
        if not self._inited:
            self.begin()
        self.disp.LCD_ShowImage(image, 0, 0)

    def set_backlight_percent(self, percent: float):
        """Set backlight brightness 0..100 via PWM.
        Uses vendor bl_DutyCycle()."""
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        # Ensure module init so BL PWM exists
        if not self._inited:
            self.begin()
        try:
            self.disp.bl_DutyCycle(percent)
        except Exception:
            # Some vendor versions expose BL via GPIO_BL_PIN; ignore on failure
            pass

    def off(self):
        """Clear to black and set backlight to 0%."""
        try:
            self.clear((0, 0, 0))
        except Exception:
            pass
        try:
            self.set_backlight_percent(0)
        except Exception:
            pass


def vendor_off_if_available() -> bool:
    """If vendor driver is available, turn LCD off (clear and BL 0) and return True.
    Return False if vendor driver is not available or failed to init.
    """
    if not vendor_available():
        return False
    try:
        lcd = VendorLCD()
        lcd.begin()
        lcd.off()
        return True
    except Exception:
        return False
