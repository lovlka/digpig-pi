#!/usr/bin/env python3
"""
Turn the ST7735 LCD black and switch off backlight.

Usage:
  python3 lcd-off.py

Environment variables (optional overrides; defaults match many 1.44" HATs):
  LCD_PORT=0 LCD_CS=0 LCD_DC=9 LCD_BL=19 LCD_ROT=90 LCD_SPEED=4000000 python3 lcd-off.py
  LCD_BL_ACTIVE=1  # set to 0 if your backlight is active-low
  LCD_PRESET=waveshare144  # applies common pins: DC=25, RST=27, BL=24, CS=0, ROT=0
  LCD_RST=27       # optional reset pin if available

Requires:
  pip install st7735 pillow
"""
import os
import sys
from pathlib import Path
from PIL import Image

# Prefer vendor driver if available via lcd_util
try:
    import lcd_util  # local helper wrapping vendor code
    if lcd_util.vendor_off_if_available():
        print("[lcd-off] used vendor driver to clear and turn backlight off.")
        sys.exit(0)
except Exception:
    pass

try:
    import st7735
except ImportError:
    print("Error: st7735 library not found. Install with: pip install st7735", file=sys.stderr)
    sys.exit(1)

# Load persisted env from lcd.env if present

def _load_env_file(fn: Path):
    try:
        if fn.exists():
            for line in fn.read_text().splitlines():
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if '=' not in s:
                    continue
                k, v = s.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

_load_env_file(Path(__file__).resolve().parent / 'lcd.env')

# Read configuration/env
PORT = int(os.getenv("LCD_PORT", "0"))
CS = int(os.getenv("LCD_CS", "1"))
DC = int(os.getenv("LCD_DC", "9"))
BL = int(os.getenv("LCD_BL", "19"))
ROT = int(os.getenv("LCD_ROT", "90"))
SPEED = int(os.getenv("LCD_SPEED", "4000000"))
RST = int(os.getenv("LCD_RST", "-1"))  # -1 means not used
PRESET = os.getenv("LCD_PRESET", "").lower()
BL_ACTIVE_HIGH = os.getenv("LCD_BL_ACTIVE", "1") in ("1","true","True","yes","on")

# Apply known preset defaults unless overridden explicitly via env
if PRESET in ("waveshare144", "waveshare-1.44", "waveshare"):
    if os.getenv("LCD_DC") is None:
        DC = 25
    if os.getenv("LCD_BL") is None:
        BL = 24
    if os.getenv("LCD_RST") is None:
        RST = 27
    if os.getenv("LCD_CS") is None:
        CS = 0
    if os.getenv("LCD_PORT") is None:
        PORT = 0
    if os.getenv("LCD_ROT") is None:
        ROT = 0

print(f"[lcd-off] preset={PRESET or '-'} port={PORT} cs={CS} dc={DC} rst={RST if RST>=0 else '-'} bl={BL} rot={ROT} speed={SPEED} bl_active_high={BL_ACTIVE_HIGH}")

# Optional manual reset pulse (helps if driver doesn't accept rst kw)
if RST >= 0:
    try:
        import RPi.GPIO as GPIO
        import time as _t
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RST, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.output(RST, GPIO.LOW)
        _t.sleep(0.05)
        GPIO.output(RST, GPIO.HIGH)
        _t.sleep(0.05)
        print(f"[lcd-off] manual reset pulse on GPIO{RST}")
    except Exception as e:
        print(f"[lcd-off] manual reset skipped (GPIO lib not available?): {e}")

# Create display with best-compat args first
try:
    kwargs = dict(port=PORT, cs=CS, dc=DC, backlight=BL, rotation=ROT, spi_speed_hz=SPEED)
    if RST >= 0:
        kwargs["rst"] = RST
    disp = st7735.ST7735(**kwargs)
except TypeError:
    # Fallback for older forks
    disp = st7735.ST7735(port=PORT, cs=CS, rotation=ROT, spi_speed_hz=SPEED)

# Init
try:
    disp.begin()
except Exception as e:
    print(f"[lcd-off] ERROR: disp.begin() failed: {e}", file=sys.stderr)
    sys.exit(2)

# Clear to black at native size
W, H = disp.width, disp.height
black = Image.new('RGB', (W, H), (0, 0, 0))
try:
    disp.display(black)
    print("[lcd-off] screen cleared to black")
except Exception as e:
    print(f"[lcd-off] WARNING: could not draw black frame: {e}")

# Try to switch backlight off
# Many drivers offer set_backlight(True/False). If absent, we cannot directly toggle BL here.
try:
    if hasattr(disp, 'set_backlight'):
        # Respect polarity indirectly by driver; if polarity kw is unsupported, driver usually knows board wiring.
        disp.set_backlight(False)
        print("[lcd-off] backlight: requested OFF")
    else:
        # As a last resort, if BL line is handled via GPIO by driver, it might not expose control; do nothing.
        print("[lcd-off] backlight control not exposed by driver; if your BL is active-low, consider wiring/polarity options")
except Exception as e:
    print(f"[lcd-off] backlight control failed: {e}")

# Done
