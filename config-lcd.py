#!/usr/bin/env python3
"""
One-time configuration helper for LCD environment variables.

This script helps you save your LCD setup values so other scripts (lcd-test.py,
lcd-ping.py, lcd-off.py) can load them automatically without needing to set
environment variables each time.

What it does:
- Interactively prompt for common LCD_* parameters with sensible defaults.
- Save them into a local lcd.env file in KEY=VALUE form.
- Optionally install them system-wide for your user by appending export lines
  to ~/.profile (requires you to restart the shell or source the file).

Usage:
  python3 config-lcd.py                 # interactive, writes lcd.env
  python3 config-lcd.py --non-interactive KEY=VALUE ...
  python3 config-lcd.py --install-global   # append exports to ~/.profile from lcd.env

Examples:
  python3 config-lcd.py --non-interactive LCD_PRESET=waveshare144 LCD_PORT=0 LCD_CS=0 LCD_DC=25 LCD_BL=24 LCD_RST=27 LCD_ROT=0 LCD_SPEED=4000000 LCD_WIDTH=128 LCD_HEIGHT=128 LCD_OX=2 LCD_OY=3
  python3 config-lcd.py --install-global

Notes:
- lcd.env is used by the scripts automatically if present in the same directory.
- To remove global exports, manually edit ~/.profile and delete the added block.
"""
import os
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
ENV_FILE = REPO_DIR / 'lcd.env'
PROFILE_FILE = Path.home() / '.profile'

# Keys we support (order matters for prompt)
KEYS = [
    'LCD_PRESET',      # e.g., waveshare144
    'LCD_PORT',        # 0 or 1
    'LCD_CS',          # 0 or 1
    'LCD_DC',          # GPIO
    'LCD_BL',          # GPIO
    'LCD_RST',         # GPIO or -1
    'LCD_ROT',         # 0/90/180/270
    'LCD_SPEED',       # Hz
    'LCD_WIDTH',       # panel width
    'LCD_HEIGHT',      # panel height
    'LCD_OX',          # offset x
    'LCD_OY',          # offset y
    'LCD_INVERT',      # 0/1
    'LCD_BL_ACTIVE',   # 1 if active-high, 0 if active-low
    'BTN_UP',         # joystick up (BCM)
    'BTN_DOWN',       # joystick down (BCM)
    'BTN_LEFT',       # joystick left (BCM)
    'BTN_RIGHT',      # joystick right (BCM)
    'BTN_CENTER',     # joystick press (BCM)
    'BTN_A',          # button A (if present)
    'BTN_B',          # button B (if present)
    'BTN_ACTIVE_LOW', # 1 if buttons are active-low
    'BTN_DEBOUNCE_MS',# debounce in ms
]

DEFAULTS = {
    # Defaults match Waveshare 1.44" HAT when using our preset
    'LCD_PRESET': 'waveshare144',
    'LCD_PORT': '0',
    'LCD_CS': '0',
    'LCD_DC': '25',
    'LCD_BL': '24',
    'LCD_RST': '27',
    'LCD_ROT': '0',
    'LCD_SPEED': '4000000',
    'LCD_WIDTH': '128',
    'LCD_HEIGHT': '128',
    'LCD_OX': '2',
    'LCD_OY': '3',
    'LCD_INVERT': '0',
    'LCD_BL_ACTIVE': '1',
    # Button defaults (Waveshare 1.44" HAT typical)
    'BTN_UP': '6',
    'BTN_DOWN': '19',
    'BTN_LEFT': '5',
    'BTN_RIGHT': '26',
    'BTN_CENTER': '13',
    'BTN_A': '21',
    'BTN_B': '20',
    'BTN_ACTIVE_LOW': '1',
    'BTN_DEBOUNCE_MS': '50',
}

def parse_kv_args(args):
    parsed = {}
    for a in args:
        if '=' not in a:
            print(f"Ignoring argument (not KEY=VALUE): {a}")
            continue
        k, v = a.split('=', 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        parsed[k] = v
    return parsed


def load_existing_env_file(path: Path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if '=' not in s:
            continue
        k, v = s.split('=', 1)
        values[k.strip()] = v.strip()
    return values


def write_env_file(path: Path, values: dict):
    lines = [
        '# Saved by config-lcd.py',
    ]
    for k in KEYS:
        if k in values:
            lines.append(f'{k}={values[k]}')
    path.write_text('\n'.join(lines) + '\n')
    print(f"Wrote {path}")


def install_global_exports(values: dict):
    block_begin = '# >>> lcd.env (config-lcd.py) >>>'
    block_end = '# <<< lcd.env (config-lcd.py) <<<'
    exports = [block_begin]
    for k in KEYS:
        if k in values:
            exports.append(f'export {k}="{values[k]}"')
    exports.append(block_end)
    block = '\n'.join(exports) + '\n'

    # Remove previous block if exists
    if PROFILE_FILE.exists():
        txt = PROFILE_FILE.read_text()
    else:
        txt = ''
    if block_begin in txt and block_end in txt:
        pre = txt.split(block_begin)[0]
        post = txt.split(block_end, 1)[1]
        txt = pre + post
    txt = txt.rstrip() + '\n\n' + block
    PROFILE_FILE.write_text(txt)
    print(f"Appended exports to {PROFILE_FILE}. Restart your shell or run: source {PROFILE_FILE}")


def interactive_setup():
    print("LCD configuration (press Enter to accept defaults).\n")
    existing = load_existing_env_file(ENV_FILE)
    values = {}
    for k in KEYS:
        default = existing.get(k, os.getenv(k, DEFAULTS.get(k, '')))
        prompt = f"{k} [{default}]: "
        val = input(prompt).strip()
        if not val:
            val = default
        values[k] = val
    return values


def main():
    args = sys.argv[1:]
    if '--install-global' in args:
        # Load from lcd.env and install
        vals = load_existing_env_file(ENV_FILE)
        if not vals:
            print(f"No {ENV_FILE.name} found. Run interactive setup first or use --non-interactive.")
            sys.exit(1)
        install_global_exports(vals)
        return

    if '--non-interactive' in args:
        idx = args.index('--non-interactive')
        kv_args = parse_kv_args(args[idx+1:])
        if not kv_args:
            print("No KEY=VALUE pairs provided after --non-interactive")
            sys.exit(2)
        write_env_file(ENV_FILE, kv_args)
        print("Done. Scripts will auto-load lcd.env if present.")
        return

    # Default: interactive
    vals = interactive_setup()
    write_env_file(ENV_FILE, vals)
    print("Done. Optionally install to ~/.profile with: python3 config-lcd.py --install-global")


if __name__ == '__main__':
    main()
