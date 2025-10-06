#!/usr/bin/env python3
"""
Display a message on a 1.44" 120x120 ST7735 SPI LCD (e.g., Pi Zero 2 W + LCD HAT).

Usage:
  python3 lcd-test.py "Hello World"  # custom message

Env overrides (optional):
  LCD_PORT=0 LCD_CS=0 LCD_DC=9 LCD_BL=19 LCD_ROT=90 LCD_SPEED=4000000 python3 lcd-test.py

Requires:
  pip install st7735 pillow
Ensure SPI is enabled on the Pi.
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    import st7735
except ImportError as e:
    print("Error: st7735 library not found. Install with: pip install st7735", file=sys.stderr)
    raise

# Load persisted env from lcd.env if present, then read environment
# This allows one-time configuration via config-lcd.py

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

PORT = int(os.getenv("LCD_PORT", "0"))
CS = int(os.getenv("LCD_CS", "0"))
DC = int(os.getenv("LCD_DC", "9"))
BL = int(os.getenv("LCD_BL", "19"))
ROT = int(os.getenv("LCD_ROT", "90"))
SPEED = int(os.getenv("LCD_SPEED", "4000000"))
WIDTH = int(os.getenv("LCD_WIDTH", "128"))
HEIGHT = int(os.getenv("LCD_HEIGHT", "128"))
OFFSET_X = int(os.getenv("LCD_OX", "0"))
OFFSET_Y = int(os.getenv("LCD_OY", "0"))
INVERT = os.getenv("LCD_INVERT", "0") in ("1", "true", "True", "yes", "on")
BL_ACTIVE_HIGH = os.getenv("LCD_BL_ACTIVE", "1") in ("1", "true", "True", "yes", "on")
TESTPAT = os.getenv("LCD_TESTPAT", "0") in ("1", "true", "True", "yes", "on")
RST = int(os.getenv("LCD_RST", "-1"))  # -1 means not used
PRESET = os.getenv("LCD_PRESET", "").lower()

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
        ROT = 90
    # Use full 128x128 controller with panel offset so the 120x120 window is fully covered
    if os.getenv("LCD_WIDTH") is None:
        WIDTH = 128
    if os.getenv("LCD_HEIGHT") is None:
        HEIGHT = 128
    if os.getenv("LCD_OX") is None:
        OFFSET_X = 2
    if os.getenv("LCD_OY") is None:
        OFFSET_Y = 3

print(f"[lcd-test] preset={PRESET or '-'} port={PORT} cs={CS} dc={DC} rst={RST if RST>=0 else '-'} bl={BL} rot={ROT} speed={SPEED} width={WIDTH} height={HEIGHT} ox={OFFSET_X} oy={OFFSET_Y} invert={INVERT} bl_active_high={BL_ACTIVE_HIGH}")

# Initialize display
# Note: Many 1.44" HATs are 128x128 panels with a 120x120 visible window; offsets vary by panel variant.
# Some versions of the st7735 library do not accept extended keyword args. We try extended first, then fall back.
# If we have a reset pin, try a manual reset pulse before init (in case driver doesn't accept rst kw)
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
        print(f"[lcd-test] manual reset pulse on GPIO{RST}")
    except Exception as e:
        print(f"[lcd-test] manual reset skipped (GPIO lib not available?): {e}")

try:
    kwargs = dict(
        port=PORT,
        cs=CS,
        dc=DC,
        backlight=BL,
        rotation=ROT,
        spi_speed_hz=SPEED,
        width=WIDTH,
        height=HEIGHT,
        offset_left=OFFSET_X,
        offset_top=OFFSET_Y,
        invert=INVERT,
    )
    # Some libs support these kwargs; include them conditionally
    kwargs["backlight_active_high"] = BL_ACTIVE_HIGH
    if RST >= 0:
        kwargs["rst"] = RST
    disp = st7735.ST7735(**kwargs)
except TypeError:
    # Fallback to minimal constructor for older lib versions
    disp = st7735.ST7735(
        port=PORT,
        cs=CS,
        dc=DC,
        backlight=BL,
        rotation=ROT,
        spi_speed_hz=SPEED
    )

disp.begin()
# Try to apply runtime settings where supported
# Ensure backlight on (some panels boot with BL off)
for val in (True,):
    try:
        disp.set_backlight(val)
        break
    except Exception:
        break
# Try invert after begin if method exists
try:
    if INVERT and hasattr(disp, "invert"):  # some libs provide invert()
        disp.invert(True)
except Exception:
    pass

# Create a canvas
width = disp.width
height = disp.height
image = Image.new('RGB', (width, height), color=(0, 0, 0))
draw = ImageDraw.Draw(image)

# Choose message
message = " ".join(sys.argv[1:]).strip() or "Hej Pi!"

# Load a font and auto-size to fit
try:
    # Try a nicer truetype font if available
    font_path_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font_path = next((p for p in font_path_candidates if os.path.exists(p)), None)
    if font_path:
        # Binary search font size to fit within width with small margins
        max_size = height  # start upper bound
        min_size = 6
        best_font = ImageFont.truetype(font_path, 12)
        while min_size <= max_size:
            mid = (min_size + max_size) // 2
            f = ImageFont.truetype(font_path, mid)
            bbox = draw.textbbox((0, 0), message, font=f)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            if tw <= width - 8 and th <= height - 8:
                best_font = f
                min_size = mid + 1
            else:
                max_size = mid - 1
        font = best_font
    else:
        font = ImageFont.load_default()
except Exception:
    font = ImageFont.load_default()

# Compute centered position
bbox = draw.textbbox((0, 0), message, font=font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
x = max(0, (width - tw) // 2)
y = max(0, (height - th) // 2)

# Optional background rectangle with padding for readability
padding = 2
bg_rect = (max(0, x - padding), max(0, y - padding), min(width, x + tw + padding), min(height, y + th + padding))
draw.rectangle(bg_rect, fill=(0, 0, 0))

# Draw text in a bright color
text_color = (255, 255, 0)
draw.text((x, y), message, font=font, fill=text_color)

# Optional test pattern to validate panel updates
if TESTPAT:
    # Draw border and color bars
    draw.rectangle((0, 0, width-1, height-1), outline=(0, 255, 0))
    bar_w = max(1, width // 6)
    colors = [(255,0,0),(0,255,0),(0,0,255),(255,255,0),(0,255,255),(255,0,255)]
    for i, c in enumerate(colors):
        draw.rectangle((i*bar_w, 0, (i+1)*bar_w-1, height-1), outline=None, fill=c)
    draw.text((2, 2), "TEST", font=ImageFont.load_default(), fill=(0,0,0))

# Display on LCD
disp.display(image)
print("[lcd-test] Frame displayed.")
