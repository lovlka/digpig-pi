#!/usr/bin/env python3
"""
Read buttons and joystick on the Waveshare 1.44" ST7735S LCD HAT and log events.

- Prints press and release events with timestamps to stdout.
- Defaults to Waveshare 1.44" HAT GPIO mapping; can be overridden via lcd.env or env vars.
- Runs until Ctrl+C.

Usage:
  python3 lcd-input.py

Requirements on the Pi:
  pip install RPi.GPIO

Notes:
- If a pin cannot register edge detection (e.g., reserved by kernel or already in use),
  this script will fall back to polling that pin so you still get logs.
- Set any BTN_* to -1 in lcd.env to disable that button entirely.
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Load persisted env from lcd.env if present, then read environment

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

try:
    import RPi.GPIO as GPIO
except Exception as e:
    print("Error: RPi.GPIO not available. Install on the Pi: sudo apt install -y python3-rpi.gpio", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)

# Default Waveshare 1.44" HAT (commonly):
# Joystick: UP/DOWN/LEFT/RIGHT/CENTER; Extra buttons A/B may exist on some boards.
# Below defaults are typical for Waveshare ST7735S HAT v1.x:
DEFAULT_PINS = {
    'BTN_UP': '6',       # BCM 6
    'BTN_DOWN': '19',    # BCM 19
    'BTN_LEFT': '5',     # BCM 5
    'BTN_RIGHT': '26',   # BCM 26
    'BTN_CENTER': '13',  # BCM 13 (joystick press)
    'BTN_A': '21',       # BCM 21 (if present)
    'BTN_B': '20',       # BCM 20 (if present)
    'BTN_ACTIVE_LOW': '1', # buttons pull-up, active-low
}

# Load pins from env with defaults
PINS = {k: int(os.getenv(k, v)) for k, v in DEFAULT_PINS.items() if k != 'BTN_ACTIVE_LOW'}
ACTIVE_LOW = os.getenv('BTN_ACTIVE_LOW', DEFAULT_PINS['BTN_ACTIVE_LOW']) in ("1","true","True","yes","on")

# Filter out pins set to -1 to disable a button
PINS = {name: pin for name, pin in PINS.items() if pin >= 0}

print("[lcd-input] Using BCM pins:")
for name, pin in PINS.items():
    print(f"  - {name}: GPIO{pin}")
print(f"[lcd-input] Active low: {ACTIVE_LOW}")

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Configure each button as input with pull-up (active-low) or pull-down (active-high)
for name, pin in PINS.items():
    if ACTIVE_LOW:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    else:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Helper to read logical pressed state

def is_pressed(pin: int) -> bool:
    val = GPIO.input(pin)
    return (val == GPIO.LOW) if ACTIVE_LOW else (val == GPIO.HIGH)

# Debounce settings
BOUNCE_MS = int(os.getenv('BTN_DEBOUNCE_MS', '50'))

# Track last state to emit release events
last_state = {name: is_pressed(pin) for name, pin in PINS.items()}

# Emit initial states if pressed at startup
now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
for name, state in last_state.items():
    if state:
        print(f"[{now}] [input] {name} pressed (startup)")

# Prepare event-driven and polled sets
POLLED = {}

# Edge callbacks

def make_callback(name: str, pin: int):
    def _cb(channel):
        # Small sleep to let the signal settle (software debounce)
        time.sleep(BOUNCE_MS / 1000.0)
        state = is_pressed(pin)
        prev = last_state.get(name, None)
        if prev == state:
            return
        last_state[name] = state
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{ts}] [input] {name} {'pressed' if state else 'released'}")
    return _cb

# Register both edges to catch press and release; if it fails, fall back to polling
EVENT_PINS = []
for name, pin in PINS.items():
    try:
        GPIO.add_event_detect(pin, GPIO.BOTH, callback=make_callback(name, pin), bouncetime=BOUNCE_MS)
        EVENT_PINS.append((name, pin))
    except Exception as e:
        print(f"[lcd-input] WARNING: could not add event for {name} (GPIO{pin}): {e}")
        POLLED[name] = pin

if EVENT_PINS:
    print("[lcd-input] Event-driven pins:")
    for name, pin in EVENT_PINS:
        print(f"  - {name}: GPIO{pin}")
if POLLED:
    print("[lcd-input] Polled pins (fallback):")
    for name, pin in POLLED.items():
        print(f"  - {name}: GPIO{pin}")

print("[lcd-input] Listening for button/joystick events. Press Ctrl+C to exit.")

try:
    poll_interval = max(0.02, BOUNCE_MS / 1000.0)  # seconds
    while True:
        # Poll fallback pins and emit on state change
        if POLLED:
            for name, pin in POLLED.items():
                state = is_pressed(pin)
                prev = last_state.get(name)
                if prev != state:
                    last_state[name] = state
                    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{ts}] [input] {name} {'pressed' if state else 'released'}")
        time.sleep(poll_interval)
except KeyboardInterrupt:
    print("\n[lcd-input] Exiting on Ctrl+C")
finally:
    GPIO.cleanup()
    print("[lcd-input] GPIO cleaned up")
