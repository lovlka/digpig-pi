#!/usr/bin/env python3
"""
Shared GPIO button monitoring utilities for Raspberry Pi using RPi.GPIO.

Goals:
- Provide a small, dependency-light helper to watch a button with debouncing
  and trigger callbacks on press/release.
- Match the usage patterns currently duplicated in hello-on-center.py and
  flask_server.py.

Notes:
- Active-low buttons (with pull-up) are common on the Waveshare 1.44" HAT.
- If RPi.GPIO is unavailable (e.g., dev machine), the helpers become no-ops.
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:
    GPIO = None  # type: ignore


@dataclass
class ButtonConfig:
    pin: int
    pull_up: bool = True            # True => use pull-up, active-low button
    debounce_ms: int = 150
    poll_interval_s: float = 0.02

    @property
    def active_low(self) -> bool:
        return self.pull_up


class ButtonWatcher:
    def __init__(self, config: ButtonConfig,
                 on_press: Optional[Callable[[], None]] = None,
                 on_release: Optional[Callable[[], None]] = None):
        self.config = config
        self.on_press = on_press
        self.on_release = on_release
        self._running = False
        self._last_val: Optional[int] = None
        self._last_change_ms: float = 0.0

    def setup(self) -> bool:
        if GPIO is None:
            return False
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            pud = GPIO.PUD_UP if self.config.pull_up else GPIO.PUD_DOWN
            GPIO.setup(self.config.pin, GPIO.IN, pull_up_down=pud)
            self._last_val = GPIO.input(self.config.pin)
            self._last_change_ms = time.time() * 1000.0
            return True
        except Exception:
            return False

    def loop(self):
        """Blocking loop until KeyboardInterrupt. Calls callbacks on edges.
        Make sure to call setup() first. Safe no-op if GPIO missing.
        """
        if GPIO is None:
            return
        self._running = True
        try:
            while self._running:
                val = GPIO.input(self.config.pin)
                now = time.time() * 1000.0
                if self._last_val is None:
                    self._last_val = val
                if val != self._last_val and (now - self._last_change_ms) > self.config.debounce_ms:
                    self._last_change_ms = now
                    prev = self._last_val
                    self._last_val = val
                    # Determine press/release respecting active level
                    active_level = GPIO.LOW if self.config.active_low else GPIO.HIGH
                    if val == active_level:
                        if self.on_press:
                            try:
                                self.on_press()
                            except Exception:
                                pass
                    else:
                        if self.on_release:
                            try:
                                self.on_release()
                            except Exception:
                                pass
                time.sleep(self.config.poll_interval_s)
        except KeyboardInterrupt:
            pass
        except Exception:
            # Swallow GPIO/IO errors to avoid crashing callers
            pass
        finally:
            self.cleanup()

    def stop(self):
        self._running = False

    def cleanup(self):
        if GPIO is None:
            return
        try:
            GPIO.cleanup()
        except Exception:
            pass


def watch_button(pin: int,
                 on_press: Callable[[], None],
                 on_release: Optional[Callable[[], None]] = None,
                 debounce_ms: int = 150,
                 poll_interval_s: float = 0.02,
                 pull_up: bool = True):
    """Convenience function similar to prior inlined loops.

    Blocks and monitors the given pin, invoking callbacks on press/release.
    Returns when interrupted or on GPIO error. No-ops if RPi.GPIO is missing.
    """
    cfg = ButtonConfig(pin=pin, pull_up=pull_up, debounce_ms=debounce_ms, poll_interval_s=poll_interval_s)
    watcher = ButtonWatcher(cfg, on_press=on_press, on_release=on_release)
    ok = watcher.setup()
    if not ok:
        return
    watcher.loop()
