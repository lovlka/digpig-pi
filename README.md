# Raspberry PI playground

## Goal
Show a custom message on a Raspberry Pi Zero 2 W using a 1.44" 120x120 ST7735 LCD HAT.

## Actions taken so far
1. Created image with Raspberry Pi Imager
   - Raspberry Pi OS (x64) Desktop
   - User/Pass: victor/lovlka
   - Hostname: digpig.local
   - WiFi: Wi‑Fi
2. Enable SPI
   - `sudo raspi-config`
   - Interface Options -> SPI -> Yes
3. Install Python and create venv
   - `sudo apt update && sudo apt install -y python3-pip python3-venv`
   - `mkdir ~/lcd-test && cd ~/lcd-test`
   - `python3 -m venv venv`
   - `source venv/bin/activate`
   - `pip install st7735 pillow`
4. Copy script to PI
   - `scp ./lcd-test.py victor@digpig.local:~/lcd-test/`

## Wiring / Pins
The defaults in `lcd-test.py` suit many Pimoroni/clone ST7735 1.44" HATs:
- SPI Port: 0
- CS: 0
- DC: GPIO 9
- Backlight: GPIO 19
- Rotation: 90°
- SPI Speed: 4 MHz
Override via env vars if your HAT differs: `LCD_PORT`, `LCD_CS`, `LCD_DC`, `LCD_BL`, `LCD_ROT`, `LCD_SPEED`.

## Usage
SSH to the Pi, activate venv and run:
```
cd ~/lcd-test
source venv/bin/activate
python3 lcd-test.py "Hello DigPig!"
```
Or with custom pins/rotation:
```
LCD_DC=25 LCD_BL=18 LCD_ROT=0 python3 lcd-test.py "Hej Pi!"
```

## Notes
- Some 1.44" modules are physically 128x128 with a 120x120 visible area. If nothing shows or it’s shifted, try offsets and size.
- If text appears rotated or off-screen, try `LCD_ROT=0`, `90`, `180`, or `270`.
- If you get `ImportError: st7735`, install it in your venv: `pip install st7735`.

## Troubleshooting: nothing on screen
Try these in order (run one command per try):
- Ensure backlight is wired and on: many HATs use BL=GPIO19 active-high. If your board is active-low, add `LCD_BL_ACTIVE=0`.
- Use a visible test pattern and print diagnostics:
```
LCD_TESTPAT=1 python3 lcd-test.py
```
- Force common variants (each line is a separate test):
```
# 1) 128x128 panel, 120x120 window at +(2,3), rotated 0
LCD_WIDTH=128 LCD_HEIGHT=128 LCD_OX=2 LCD_OY=3 LCD_ROT=0 python3 lcd-test.py
# 2) 128x128 panel, window at + (1,2), rotated 90 (common for 1.44" HATs)
LCD_WIDTH=128 LCD_HEIGHT=128 LCD_OX=1 LCD_OY=2 LCD_ROT=90 python3 lcd-test.py
# 3) Inverted colors (some panels need it)
LCD_INVERT=1 python3 lcd-test.py
# 4) Different DC/BL pins (example)
LCD_DC=25 LCD_BL=18 python3 lcd-test.py
```
- If you see backlight but no image, try lowering SPI speed: `LCD_SPEED=1000000`.
- If still blank, try CS=1: `LCD_CS=1`.

Note: The script auto-detects the st7735 library capabilities. If your installed version doesn’t support extended init kwargs (offsets/invert/backlight polarity), it will fall back to a minimal init and then try to apply invert/backlight at runtime where possible.

## One-time configuration
You can save your LCD settings once and reuse them automatically:

- Run the interactive configurator:
```
python3 config-lcd.py
```
This writes an lcd.env file in the project directory. All LCD scripts auto-load it.

- To install globally for your user (so settings are available in every shell):
```
python3 config-lcd.py --install-global
# then restart your shell or:
source ~/.profile
```

- Non-interactive example:
```
python3 config-lcd.py --non-interactive LCD_PRESET=waveshare144 LCD_PORT=0 LCD_CS=0 LCD_DC=25 LCD_BL=24 LCD_RST=27 LCD_ROT=0 LCD_SPEED=4000000 LCD_WIDTH=128 LCD_HEIGHT=128 LCD_OX=2 LCD_OY=3
```

The scripts still accept environment overrides if you pass them at runtime. 

## Environment variables supported
- LCD_PORT, LCD_CS, LCD_DC, LCD_BL, LCD_ROT, LCD_SPEED
- LCD_WIDTH, LCD_HEIGHT, LCD_OX, LCD_OY
- LCD_INVERT, LCD_BL_ACTIVE (1 or 0), LCD_TESTPAT (1 to show test pattern)

## Quick connectivity check
Try the minimal color-cycle test first. You should see black → white → red → green → blue fill the screen.
```
cd ~/lcd-test
source venv/bin/activate
python3 lcd-ping.py
```
If nothing appears:
- Ensure the backlight is on or try active-low: `LCD_BL_ACTIVE=0 python3 lcd-ping.py`
- Lower SPI speed: `LCD_SPEED=1000000 python3 lcd-ping.py`
- Try the other chip select: `LCD_CS=1 python3 lcd-ping.py`
- Try different rotation if the HAT is mounted differently: `LCD_ROT=0` or `90`.
- Increase dwell time to make changes obvious: `LCD_DELAY_MS=1000`.

### Waveshare 1.44" LCD HAT (ST7735S) preset
This board typically uses: CS=CE0, DC=GPIO25, RST=GPIO27, BL=GPIO24.
Use the preset for a quick test:
```
LCD_PRESET=waveshare144 python3 lcd-ping.py
```
If still blank, also try low SPI speed and alternate CS:
```
LCD_PRESET=waveshare144 LCD_SPEED=1000000 python3 lcd-ping.py
LCD_PRESET=waveshare144 LCD_CS=1 LCD_SPEED=1000000 python3 lcd-ping.py
```
The preset also applies panel offsets so the full 120x120 visible area is used (controller is 128x128 with offsets 2,3 at ROT=0). You can override with LCD_WIDTH/LCD_HEIGHT/LCD_OX/LCD_OY if needed.
After connectivity is confirmed, use lcd-test.py for messages and patterns, e.g.:
```
LCD_PRESET=waveshare144 python3 lcd-test.py "Hello DigPig!"
```

## Turn screen off (clear and backlight off)
Use the minimal off script to blank the LCD and switch the backlight off:
```
python3 lcd-off.py
```
If you use the Waveshare 1.44" HAT, the preset helps:
```
LCD_PRESET=waveshare144 python3 lcd-off.py
```
If your backlight is active-low and stays on, try:
```
LCD_BL_ACTIVE=0 python3 lcd-off.py
```

## Read buttons and joystick
This script logs button/joystick events to the console. Defaults assume the Waveshare 1.44" LCD HAT.
- Defaults (BCM): UP=6, DOWN=19, LEFT=5, RIGHT=26, CENTER=13, A=21, B=20; active-low with pull-ups.
- You can override pins in lcd.env via keys: BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_CENTER, BTN_A, BTN_B, BTN_ACTIVE_LOW (1/0), BTN_DEBOUNCE_MS.
- Tip: set any BTN_* to -1 in lcd.env to disable that button (useful if a pin is reserved or not present on your HAT).
- If edge detection cannot be set on a pin (kernel/driver conflict), the script auto-falls back to polling that pin and will still log events.

Usage:
```
python3 lcd-input.py
```
Press buttons while watching the SSH console; you should see lines like:
```
[12:34:56.789] [input] BTN_UP pressed
[12:34:56.950] [input] BTN_UP released
```

Troubleshooting buttons:
- GPIO20/21 can be used by some configurations (I2C or other overlays). If you get “Failed to add edge detection” for BTN_B (GPIO20) or BTN_A (GPIO21):
  - Either let the script’s polling fallback handle it, or
  - Reassign BTN_B/BTN_A to a free BCM pin in lcd.env, or set to -1 to disable.
  - Ensure no other process exports or uses those pins.

## Auto-start on boot (systemd)
This service is configured to run your script using the project's virtualenv at /home/victor/lcd-test/venv so all Python packages are found.

1) Prepare the venv and install dependencies (run on the Pi):
```
cd ~/lcd-test
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install st7735 pillow RPi.GPIO
```

2) Install the service and enable it:
```
sudo cp ~/lcd-test/digpig-hello.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable digpig-hello.service
sudo systemctl start digpig-hello.service
```

3) Check status/logs:
```
systemctl status digpig-hello.service
journalctl -u digpig-hello.service -f
```

Notes:
- The service runs ExecStart=/home/victor/lcd-test/venv/bin/python /home/victor/lcd-test/hello-on-center.py and sets PATH to the venv bin. If your username or path differs, edit digpig-hello.service accordingly.
- If you see ModuleNotFoundError or ImportError in logs, verify the venv path and that dependencies are installed inside that venv.

Manual run (without service):
```
source ~/lcd-test/venv/bin/activate
python3 hello-on-center.py
```

## Web server (Flask) to display text via HTTP
Endpoints:
- POST /display with JSON {"text":"Hej"} to show text on LCD
- GET /display returns current text
- GET /health returns status

Run once (in venv):
```
cd ~/lcd-test
source venv/bin/activate
pip install flask st7735 pillow RPi.GPIO
LCD_PRESET=waveshare FLASK_PORT=8080 python3 flask_server.py
```

Send a message from another device on the network:
```
curl -X POST http://digpig.local:8080/display -H 'Content-Type: application/json' -d '{"text":"Hej från appen"}'
```

Auto-start on boot:
```
sudo cp ~/lcd-test/digpig-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable digpig-web.service
sudo systemctl start digpig-web.service
```

Logs:
```
journalctl -u digpig-web.service -f
```

Notes:
- Configure pins and options in ~/lcd-test/lcd.env (same keys as lcd-test.py), e.g. LCD_PRESET=waveshare.
- Default listen: 0.0.0.0:8080. Change via FLASK_HOST/FLASK_PORT in lcd.env.
- If you need CORS for a web app, you can reverse proxy via nginx or add Flask-Cors.

## Usable commands
```
ping digpig.local
ssh victor@digpig.local
sudo apt update && sudo apt upgrade -y
```