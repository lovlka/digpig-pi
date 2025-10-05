#!/usr/bin/env python3
"""
Minimal script for Waveshare 1.44" ST7735S LCD HAT on Raspberry Pi Zero 2 W.
- On start: clear screen to black and turn backlight off.
- When CENTER (BCM13) is pressed: show "Hello" centered (black text on white) for 5s, then black/off again.

Hardware (fixed): SPI0 CE0, DC=25, RST=27, BL=24, ROT=0, speed=4MHz; display window 128x128 with offsets (2,3).
Dependencies: pip install st7735 pillow RPi.GPIO
"""
import sys
import time
import random

import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import st7735

# Fixed pins/config for Waveshare 1.44" HAT
PORT = 0
CS = 0
DC = 25
RST = 27
BL = 24
ROT = 0
SPEED = 4_000_000
WIDTH, HEIGHT = 128, 128
OX, OY = 2, 3
BTN_CENTER = 13  # joystick press

# Init GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(BTN_CENTER, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # active-low

# Init display
try:
    disp = st7735.ST7735(
        port=PORT,
        cs=CS,
        dc=DC,
        rst=RST,
        backlight=BL,
        rotation=ROT,
        spi_speed_hz=SPEED,
        width=WIDTH,
        height=HEIGHT,
        offset_left=OX,
        offset_top=OY,
    )
except TypeError:
    # If your st7735 version doesn't support extended args, install a newer one.
    disp = st7735.ST7735(port=PORT, cs=CS, dc=DC, backlight=BL, rotation=ROT, spi_speed_hz=SPEED)

disp.begin()

W, H = disp.width, disp.height

# Helpers

def bl(on: bool):
    try:
        disp.set_backlight(on)
    except Exception:
        pass

def show_black():
    img = Image.new('RGB', (W, H), (0, 0, 0))
    disp.display(img)

def show_hello():
    # White background
    img = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Generate random 3-digit number followed by ' kr'
    msg = f"{random.randint(100, 999)} kr"
    # Try a larger font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), msg, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = max(0, (W - tw) // 2), max(0, (H - th) // 2)
    draw.text((x, y), msg, font=font, fill=(0, 0, 0))
    disp.display(img)

# Start with screen off
show_black()
bl(False)

print("[hello-on-center] Ready. Press CENTER to show 'Hello'. Ctrl+C to exit.")

# Simple polling loop with debounce
DEBOUNCE_MS = 150
last = GPIO.input(BTN_CENTER)
last_change = 0.0

try:
    while True:
        val = GPIO.input(BTN_CENTER)  # LOW when pressed
        now = time.time() * 1000
        if val != last and (now - last_change) > DEBOUNCE_MS:
            last_change = now
            last = val
            if val == GPIO.LOW:  # pressed
                bl(True)
                show_hello()
                time.sleep(5)
                show_black()
                bl(False)
        time.sleep(0.02)
except KeyboardInterrupt:
    pass
finally:
    # Leave screen off on exit
    try:
        show_black()
        bl(False)
    except Exception:
        pass
    GPIO.cleanup()
    print("[hello-on-center] Exiting.")
