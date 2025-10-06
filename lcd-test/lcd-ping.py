#!/usr/bin/env python3
"""
Minimal connectivity test for ST7735 SPI LCD.
- Tries to turn backlight ON.
- Cycles solid colors (black, white, red, green, blue) so you can see any update.
- Uses only the widely supported args to st7735.ST7735(), then tries optional methods.

Usage:
  python3 lcd-ping.py

Environment variables (optional overrides; defaults match many 1.44" HATs):
  LCD_PORT=0 LCD_CS=0 LCD_DC=9 LCD_BL=19 LCD_ROT=90 LCD_SPEED=4000000 python3 lcd-ping.py
  LCD_BL_ACTIVE=1  # set to 0 if your backlight is active-low
  LCD_CYCLES=2     # how many color cycles
  LCD_DELAY_MS=500 # delay between colors

Requires:
  pip install st7735 pillow
"""
import os
import sys
import time
from pathlib import Path
from PIL import Image

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

PORT = int(os.getenv("LCD_PORT", "0"))
CS = int(os.getenv("LCD_CS", "1"))
DC = int(os.getenv("LCD_DC", "9"))
BL = int(os.getenv("LCD_BL", "19"))
ROT = int(os.getenv("LCD_ROT", "90"))
SPEED = int(os.getenv("LCD_SPEED", "4000000"))
RST = int(os.getenv("LCD_RST", "-1"))  # -1 means not used
PRESET = os.getenv("LCD_PRESET", "").lower()
BL_ACTIVE_HIGH = os.getenv("LCD_BL_ACTIVE", "1") in ("1","true","True","yes","on")
# Optional logical panel/window controls (some libs accept these)
WIDTH = int(os.getenv("LCD_WIDTH", "128"))
HEIGHT = int(os.getenv("LCD_HEIGHT", "128"))
OFFSET_X = int(os.getenv("LCD_OX", "0"))
OFFSET_Y = int(os.getenv("LCD_OY", "0"))
CYCLES = int(os.getenv("LCD_CYCLES", "2"))
DELAY_MS = int(os.getenv("LCD_DELAY_MS", "500"))

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
    # Use full 128x128 controller with panel offset so the 120x120 window is fully covered
    if os.getenv("LCD_WIDTH") is None:
        WIDTH = 128
    if os.getenv("LCD_HEIGHT") is None:
        HEIGHT = 128
    if os.getenv("LCD_OX") is None:
        OFFSET_X = 2
    if os.getenv("LCD_OY") is None:
        OFFSET_Y = 3

print(f"[lcd-ping] preset={PRESET or '-'} port={PORT} cs={CS} dc={DC} rst={RST if RST>=0 else '-'} bl={BL} rot={ROT} speed={SPEED} bl_active_high={BL_ACTIVE_HIGH} cycles={CYCLES} delay_ms={DELAY_MS}")

# If we have a reset pin but the driver may not take rst kw, try manual GPIO reset before begin()
manual_reset_done = False
if RST >= 0:
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RST, GPIO.OUT, initial=GPIO.HIGH)
        # Active-low reset pulse
        GPIO.output(RST, GPIO.LOW)
        time.sleep(0.05)
        GPIO.output(RST, GPIO.HIGH)
        time.sleep(0.05)
        manual_reset_done = True
        print(f"[lcd-ping] manual reset pulse on GPIO{RST}")
    except Exception as e:
        print(f"[lcd-ping] manual reset skipped (GPIO lib not available?): {e}")

# Create display with compatibility-first args; add window controls when supported
try:
    kwargs = dict(port=PORT, cs=CS, dc=DC, backlight=BL, rotation=ROT, spi_speed_hz=SPEED)
    # Try to include logical window parameters (supported by some st7735 forks)
    kwargs.update(dict(width=WIDTH, height=HEIGHT, offset_left=OFFSET_X, offset_top=OFFSET_Y))
    if RST >= 0:
        kwargs["rst"] = RST
    disp = st7735.ST7735(**kwargs)
except TypeError:
    # Extreme fallback without dc/backlight/rst (some forks have different sigs)
    disp = st7735.ST7735(port=PORT, cs=CS, rotation=ROT, spi_speed_hz=SPEED)

# Power up / init
try:
    disp.begin()
except Exception as e:
    print(f"[lcd-ping] ERROR: disp.begin() failed: {e}", file=sys.stderr)
    sys.exit(2)

# Try to ensure backlight on
try:
    # If driver supports polarity, try to set ON both ways
    if hasattr(disp, 'set_backlight'):
        disp.set_backlight(True)
    else:
        # Some boards wire BL to a GPIO controlled by the driver; the call above is best effort.
        pass
    print("[lcd-ping] backlight: requested ON")
except Exception as e:
    print(f"[lcd-ping] backlight control not available ({e}) — ensure BL pin is wired and powered.")

# Prepare solid color frames at the display's reported size
W, H = disp.width, disp.height
# Draw a 1px green border frame first to verify full coverage
try:
    from PIL import ImageDraw
    border_img = Image.new('RGB', (W, H), (0, 0, 0))
    ImageDraw.Draw(border_img).rectangle((0, 0, W-1, H-1), outline=(0, 255, 0))
    disp.display(border_img)
    time.sleep(max(0.05, DELAY_MS/1000.0))
except Exception:
    pass
colors = [
    (0, 0, 0),      # black
    (255, 255, 255),# white
    (255, 0, 0),    # red
    (0, 255, 0),    # green
    (0, 0, 255),    # blue
]
frames = [Image.new('RGB', (W, H), c) for c in colors]

# Display cycle
delay = max(0.01, DELAY_MS / 1000.0)
print("[lcd-ping] starting color cycle. You should see: black → white → red → green → blue ...")
for n in range(CYCLES):
    for idx, frame in enumerate(frames):
        try:
            disp.display(frame)
            print(f"[lcd-ping] frame {n+1}.{idx+1}/{CYCLES}.{len(frames)} displayed: {colors[idx]}")
        except Exception as e:
            print(f"[lcd-ping] ERROR during display: {e}", file=sys.stderr)
            sys.exit(3)
        time.sleep(delay)

print("[lcd-ping] done. If you saw no change: check BL wiring/polarity, try LCD_CS=1, lower LCD_SPEED, or different LCD_ROT.")
