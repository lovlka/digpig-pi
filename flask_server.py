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
import os
import threading
from pathlib import Path
from flask import Flask, jsonify, request
from PIL import Image, ImageDraw, ImageFont
from display import render_centered_text_hello_style, render_centered_text_server_style, choose_font
import st7735
import time

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
# Only include keys supported by installed st7735 version.
# Older versions don't support backlight_active_high/invert/offsets/size.
# Build a minimal kwargs and then extend conservatively.
base_kwargs = dict(port=PORT, cs=CS, dc=DC, backlight=BL, rotation=ROT, spi_speed_hz=SPEED)
# Try richer kwargs first
rich_kwargs = dict(base_kwargs)
rich_kwargs.update(dict(
    width=WIDTH,
    height=HEIGHT,
    offset_left=OFFSET_X,
    offset_top=OFFSET_Y,
    invert=INVERT,
))
# Try to pass backlight_active_high only if accepted
try:
    disp = st7735.ST7735(**{**rich_kwargs, "backlight_active_high": BL_ACTIVE_HIGH, **({"rst": RST} if RST >= 0 else {})})
except TypeError:
    # Drop backlight_active_high if unsupported; also handle very old versions by falling back further
    try:
        disp = st7735.ST7735(**{**rich_kwargs, **({"rst": RST} if RST >= 0 else {})})
    except TypeError:
        # Fallback to minimal set supported by very old releases
        disp = st7735.ST7735(**base_kwargs)

try:
    disp.begin()
except OSError as e:
    # Provide a clearer message if GPIO lines are busy (e.g., another service running)
    if getattr(e, 'errno', None) == 16 or 'Device or resource busy' in str(e):
        raise SystemExit("GPIO busy. Another process/service is using the LCD pins. Stop it (e.g. systemctl stop digpig-hello.service) and try again.") from e
    raise
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
    # Delegate to shared display helper for consistent sizing
    return choose_font(message, (width, height))


def render_text(message: str):
    # Use the same visual style as the hello service (white bg, black text)
    render_centered_text_hello_style(disp, (width, height), message)


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


# Optional: Button thread for random number on press
try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:
    GPIO = None  # RPi.GPIO not available (e.g., on dev machine)

BTN_ENABLE = os.getenv('BTN_ENABLE', '1') in ("1", "true", "True", "yes", "on")
BTN_PIN = int(os.getenv('BTN_PIN', '13'))  # Waveshare center press
BTN_DEBOUNCE_MS = int(os.getenv('BTN_DEBOUNCE_MS', '150'))
BTN_SHOW_MS = int(os.getenv('BTN_SHOW_MS', '5000'))
BTN_SUFFIX = os.getenv('BTN_SUFFIX', ' kr')
BTN_MIN = int(os.getenv('BTN_MIN', '100'))
BTN_MAX = int(os.getenv('BTN_MAX', '999'))
BTN_RESTORE_PREV = os.getenv('BTN_RESTORE_PREV', '1') in ("1", "true", "True", "yes", "on")


def _bl(on: bool):
    try:
        disp.set_backlight(on)
    except Exception:
        pass


def render_random_amount():
    import random
    msg = f"{random.randint(BTN_MIN, BTN_MAX)}{BTN_SUFFIX}"
    render_centered_text_hello_style(disp, (width, height), msg)
    return msg


def _button_loop():
    # Use shared button watcher
    from button_util import watch_button
    if GPIO is None:
        return

    def on_press():
        prev = None
        with state_lock:
            prev = current_text
        _bl(True)
        shown = render_random_amount()
        time.sleep(BTN_SHOW_MS / 1000.0)
        if BTN_RESTORE_PREV:
            with state_lock:
                render_text(prev or "")
        else:
            # Clear to black
            disp.display(Image.new('RGB', (width, height), (0, 0, 0)))
            _bl(False)

    try:
        watch_button(BTN_PIN, on_press=on_press, debounce_ms=BTN_DEBOUNCE_MS, poll_interval_s=0.02, pull_up=True)
    except Exception:
        pass


if __name__ == '__main__':
    # Start button thread first so it can run alongside Flask
    if BTN_ENABLE and GPIO is not None:
        t = threading.Thread(target=_button_loop, name='btn-loop', daemon=True)
        t.start()
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', '0') in ("1", "true", "True", "yes", "on")
    # Use threaded server so requests don't block each other while drawing is serialized by lock
    app.run(host=host, port=port, debug=debug, threaded=True)
