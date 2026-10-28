"""Windows Native Win32 Input Controller for Gemini Computer Use.

Provides smooth mouse movement, clicking, dragging, scrolling,
and keyboard input using native Windows user32 APIs via ctypes.
Includes support for Unicode typing, modifier keys (Ctrl, Alt, Win, Shift),
and Emergency Corner Failsafe.
Zero external library dependencies required on Windows.
"""

import sys
import os
import time
import math
import ctypes
from ctypes import wintypes

# Define Win32 structures and constants
is_windows = sys.platform.startswith('win')

if is_windows:
    user32 = ctypes.windll.user32
    # Enable per-monitor DPI awareness so pixel coordinates match physical screen
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
else:
    user32 = None

# Mouse event constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0004
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

# Keyboard event constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Virtual Key Codes (Windows)
VK_CODES = {
    # Special & Navigation
    'return': 0x0D, 'enter': 0x0D,
    'tab': 0x09,
    'space': 0x20,
    'backspace': 0x08, 'delete': 0x2E,
    'escape': 0x1B, 'esc': 0x1B,
    'win': 0x5B, 'windows': 0x5B, 'super': 0x5B,
    'shift': 0x10, 'lshift': 0xA0, 'rshift': 0xA1,
    'control': 0x11, 'ctrl': 0x11, 'lctrl': 0xA2, 'rctrl': 0xA3,
    'alt': 0x12, 'menu': 0x12, 'lalt': 0xA4, 'ralt': 0xA5,
    'capslock': 0x14,
    'pageup': 0x21, 'pagedown': 0x22,
    'end': 0x23, 'home': 0x24,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'printscreen': 0x2C, 'insert': 0x2D,
    # Function keys
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
    'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
    'f11': 0x7A, 'f12': 0x7B,
    # Alphabet
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
    'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
    'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
    'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
    'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
    'z': 0x5A,
    # Numbers
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39
}

MODIFIER_CODES = {
    'control': 0x11, 'ctrl': 0x11,
    'alt': 0x12,
    'shift': 0x10,
    'win': 0x5B, 'windows': 0x5B
}


# Structs for SendInput
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulong)
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION)
    ]


class FailsafeTriggered(Exception):
    """Raised when emergency stop failsafe is activated (mouse in screen corner)."""
    pass


class WindowsController:
    """Controls mouse and keyboard on Windows via Win32 API."""

    def __init__(self, failsafe=True):
        self.failsafe = failsafe
        self._screen_w, self._screen_h = self.get_screen_size()

    def get_screen_size(self):
        """Returns screen width and height in pixels."""
        if not is_windows:
            return 1920, 1080
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        self._screen_w = w
        self._screen_h = h
        return w, h

    def get_mouse_position(self):
        """Returns current mouse (x, y)."""
        if not is_windows:
            return 0, 0
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def check_failsafe(self):
        """Checks if mouse is in any of the four corners of the screen."""
        if not self.failsafe:
            return
        x, y = self.get_mouse_position()
        w, h = self._screen_w, self._screen_h
        margin = 10
        in_tl = (x <= margin and y <= margin)
        in_tr = (x >= w - margin and y <= margin)
        in_bl = (x <= margin and y >= h - margin)
        in_br = (x >= w - margin and y >= h - margin)

        if in_tl or in_tr or in_bl or in_br:
            raise FailsafeTriggered(
                f"Emergency Stop! Mouse moved to screen corner ({x}, {y}). Aborting actions."
            )

    def move_to(self, target_x, target_y, duration=0.25, steps=12):
        """Smoothly moves mouse to (target_x, target_y)."""
        self.check_failsafe()
        if not is_windows:
            return

        start_x, start_y = self.get_mouse_position()
        target_x = max(0, min(self._screen_w - 1, int(target_x)))
        target_y = max(0, min(self._screen_h - 1, int(target_y)))

        if steps <= 1 or duration <= 0:
            user32.SetCursorPos(target_x, target_y)
            return

        for i in range(1, steps + 1):
            t = i / steps
            eased_t = (1.0 - math.cos(t * math.pi)) / 2.0
            cur_x = int(start_x + (target_x - start_x) * eased_t)
            cur_y = int(start_y + (target_y - start_y) * eased_t)
            user32.SetCursorPos(cur_x, cur_y)
            time.sleep(duration / steps)

        self.check_failsafe()

    def click(self, x=None, y=None, button='left', clicks=1):
        """Clicks at (x, y) or current position."""
        self.check_failsafe()
        if x is not None and y is not None:
            self.move_to(x, y, duration=0.2)

        if not is_windows:
            return

        is_left = (button.lower() == 'left')
        down_flag = MOUSEEVENTF_LEFTDOWN if is_left else MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_LEFTUP if is_left else MOUSEEVENTF_RIGHTUP

        for _ in range(clicks):
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(up_flag, 0, 0, 0, 0)
            time.sleep(0.05)

    def double_click(self, x=None, y=None):
        """Performs a double-click."""
        self.click(x, y, button='left', clicks=2)

    def right_click(self, x=None, y=None):
        """Performs a right-click."""
        self.click(x, y, button='right', clicks=1)

    def drag(self, start_x, start_y, end_x, end_y, duration=0.4, steps=15):
        """Drags mouse from (start_x, start_y) to (end_x, end_y)."""
        self.check_failsafe()
        self.move_to(start_x, start_y, duration=0.2)
        if not is_windows:
            return

        # Mouse Down
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.1)

        # Drag loop
        for i in range(1, steps + 1):
            t = i / steps
            eased_t = (1.0 - math.cos(t * math.pi)) / 2.0
            cur_x = int(start_x + (end_x - start_x) * eased_t)
            cur_y = int(start_y + (end_y - start_y) * eased_t)
            user32.SetCursorPos(cur_x, cur_y)
            time.sleep(duration / steps)

        # Mouse Up
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.1)
        self.check_failsafe()

    def scroll(self, clicks=5, direction='down'):
        """Scrolls mouse wheel. Positive is up, negative is down."""
        self.check_failsafe()
        if not is_windows:
            return

        val = int(clicks)
        delta = -120 * val if direction.lower() == 'down' else 120 * val
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        time.sleep(0.05)

    def type_text(self, text, press_enter_after=False):
        """Types Unicode text using SendInput with KEYEVENTF_UNICODE.
        
        Works regardless of active Windows keyboard layout (Russian/English)!
        """
        self.check_failsafe()
        if not is_windows:
            return

        for char in text:
            # Key Down (Unicode)
            inp_down = INPUT()
            inp_down.type = INPUT_KEYBOARD
            inp_down.union.ki.wVk = 0
            inp_down.union.ki.wScan = ord(char)
            inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
            user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))

            # Key Up (Unicode)
            inp_up = INPUT()
            inp_up.type = INPUT_KEYBOARD
            inp_up.union.ki.wVk = 0
            inp_up.union.ki.wScan = ord(char)
            inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))

            time.sleep(0.015)

        if press_enter_after:
            time.sleep(0.05)
            self.press_key('return')

    def press_key(self, key_name):
        """Presses a single key by name (e.g. 'return', 'tab', 'escape', 'win')."""
        self.check_failsafe()
        if not is_windows:
            return

        name = key_name.lower().strip()
        vk = VK_CODES.get(name)
        if vk is None:
            if len(key_name) == 1:
                self.type_text(key_name)
                return
            raise ValueError(f"Unknown key: {key_name}")

        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

    def hotkey(self, keys):
        """Executes a key combo (e.g. ['ctrl', 'c'] or ['win', 's'] or ['alt', 'f4'])."""
        self.check_failsafe()
        if not is_windows:
            return

        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split('+')]

        vks = []
        for k in keys:
            k_low = k.lower().strip()
            vk = VK_CODES.get(k_low) or MODIFIER_CODES.get(k_low)
            if vk is None:
                raise ValueError(f"Unknown key in hotkey: {k}")
            vks.append(vk)

        # Press keys down in order
        for vk in vks:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.02)

        time.sleep(0.05)

        # Release in reverse order
        for vk in reversed(vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)

        time.sleep(0.05)
