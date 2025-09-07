#!/usr/bin/env python3
"""
Simple Flask web server to receive text from an app and display it on the ST7735 LCD.

Endpoints:
- POST /display  JSON: {"text": "Hello"}  -> renders text centered on LCD
- GET  /display                              -> returns current text
- GET  /health                               -> returns status JSON

Configuration via environment variables (can also be set in lcd.env):
- FLASK_HOST (default 0.0.0.0)
- FLASK_PORT (default 8080)
- FLASK_DEBUG (0/1)
- All LCD_* variables supported by lcd-test.py (LCD_PRESET, LCD_PORT, LCD_CS, ...)

Install:
  pip install flask st7735 pillow RPi.GPIO
Run:
  LCD_PRESET=waveshare FLASK_PORT=8080 python3 flask_server.py
"""
import json
import os
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request
from PIL import Image, ImageDraw, ImageFont

# Try to import st7735; fail with clear error if missing
try:
    import st7735
except ImportError as e:
    raise SystemExit("st7735 not installed. pip install st7735") from e

# Load env file like lcd-test.py does

def _load_env_file(fn: Path):
    try:
        if fn.exists():
            for line in fn.read_text().splitlines():
                s = line.strip()
                if not s or s.startswith('#') or '=' not in s:
                    continue
                k, v = s.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

_load_env_file(Path(__file__).resolve().parent / 'lcd.env')

# Read LCD configuration (align with lcd-test.py)
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
RST = int(os.getenv("LCD_RST", "-1"))
PRESET = os.getenv("LCD_PRESET", "").lower()

# Apply preset defaults similar to lcd-test.py
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
    if os.getenv("LCD_WIDTH") is None:
        WIDTH = 128
    if os.getenv("LCD_HEIGHT") is None:
        HEIGHT = 128
    if os.getenv("LCD_OX") is None:
        OFFSET_X = 2
    if os.getenv("LCD_OY") is None:
        OFFSET_Y = 3

# Initialize display one time
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
    kwargs["backlight_active_high"] = BL_ACTIVE_HIGH
    if RST >= 0:
        kwargs["rst"] = RST
    disp = st7735.ST7735(**kwargs)
except TypeError:
    disp = st7735.ST7735(port=PORT, cs=CS, dc=DC, backlight=BL, rotation=ROT, spi_speed_hz=SPEED)

disp.begin()
# Try to turn on backlight if supported
try:
    disp.set_backlight(True)
except Exception:
    pass

width = disp.width
height = disp.height

# Global state
state_lock = threading.Lock()
current_text: str = ""


def _choose_font(message: str):
    try:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font_path = next((p for p in font_paths if os.path.exists(p)), None)
        if not font_path:
            return ImageFont.load_default()
        # Binary search size
        draw = ImageDraw.Draw(Image.new('RGB', (width, height)))
        min_size, max_size = 6, height
        best = ImageFont.truetype(font_path, 12)
        while min_size <= max_size:
            mid = (min_size + max_size) // 2
            f = ImageFont.truetype(font_path, mid)
            bbox = draw.textbbox((0, 0), message, font=f)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            if tw <= width - 8 and th <= height - 8:
                best = f
                min_size = mid + 1
            else:
                max_size = mid - 1
        return best
    except Exception:
        return ImageFont.load_default()


def render_text(message: str):
    img = Image.new('RGB', (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _choose_font(message)
    bbox = draw.textbbox((0, 0), message, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max(0, (width - tw) // 2)
    y = max(0, (height - th) // 2)
    padding = 2
    bg_rect = (
        max(0, x - padding),
        max(0, y - padding),
        min(width, x + tw + padding),
        min(height, y + th + padding),
    )
    draw.rectangle(bg_rect, fill=(0, 0, 0))
    draw.text((x, y), message, font=font, fill=(255, 255, 0))
    disp.display(img)


app = Flask(__name__)


@app.get('/health')
def health():
    return jsonify({
        'ok': True,
        'width': width,
        'height': height,
        'preset': PRESET or '-',
    })


@app.get('/display')
def get_display():
    with state_lock:
        return jsonify({'text': current_text})


@app.post('/display')
def post_display():
    global current_text
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('text') if isinstance(data, dict) else None
        if not message:
            # also accept form or query
            message = request.form.get('text') or request.args.get('text')
        if message is None:
            return jsonify({'ok': False, 'error': "Missing 'text'"}), 400
        # Limit length to avoid spending too long in font sizing
        message = str(message).strip()
        if len(message) > 256:
            message = message[:256]
        with state_lock:
            current_text = message
            render_text(message)
        return jsonify({'ok': True, 'displayed': message})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', '0') in ("1", "true", "True", "yes", "on")
    # Use threaded server so requests don't block each other while drawing is serialized by lock
    app.run(host=host, port=port, debug=debug, threaded=True)
