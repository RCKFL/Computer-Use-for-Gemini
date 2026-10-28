"""macOS Native CoreGraphics Input Controller for Gemini Computer Use.

Provides smooth mouse movement, clicking, dragging, scrolling,
and keyboard input using native macOS CoreGraphics APIs via ctypes.
Zero third-party library dependencies required.
"""

import ctypes
import math
import time
import sys

# Load CoreGraphics and ApplicationServices
cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
try:
    app_services = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
except Exception:
    app_services = None

# Structures
class CGPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]

# CoreGraphics function signatures
cg.CGMainDisplayID.restype = ctypes.c_uint32

cg.CGDisplayPixelsWide.restype = ctypes.c_size_t
cg.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]

cg.CGDisplayPixelsHigh.restype = ctypes.c_size_t
cg.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]

cg.CGEventCreate.restype = ctypes.c_void_p
cg.CGEventCreate.argtypes = [ctypes.c_void_p]

cg.CGEventGetLocation.restype = CGPoint
cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]

cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]

cg.CGEventSetIntegerValueField.restype = None
cg.CGEventSetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]

cg.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
cg.CGEventCreateScrollWheelEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32]

cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]

cg.CGEventSetFlags.restype = None
cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]

cg.CGEventKeyboardSetUnicodeString.restype = None
cg.CGEventKeyboardSetUnicodeString.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p]

cg.CGEventPost.restype = None
cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

# CoreGraphics Constants
kCGHIDEventTap = 0
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventRightMouseDown = 3
kCGEventRightMouseUp = 4
kCGEventMouseMoved = 5
kCGEventLeftMouseDragged = 6
kCGMouseButtonLeft = 0
kCGMouseButtonRight = 1
kCGMouseEventClickState = 1

# Modifier Flag Masks
kCGEventFlagMaskCommand = 0x00100000
kCGEventFlagMaskShift = 0x00020000
kCGEventFlagMaskControl = 0x00040000
kCGEventFlagMaskAlternate = 0x00080000

# macOS Virtual Key Codes
KEY_CODES = {
    # Special & Navigation
    'return': 36, 'enter': 36,
    'tab': 48,
    'space': 49,
    'backspace': 51, 'delete': 51,
    'escape': 53, 'esc': 53,
    'command': 55, 'cmd': 55,
    'shift': 56,
    'capslock': 57,
    'option': 58, 'alt': 58,
    'control': 59, 'ctrl': 59,
    'right_shift': 60,
    'right_option': 61, 'right_alt': 61,
    'right_control': 62, 'right_ctrl': 62,
    'home': 115, 'pageup': 116, 'forwarddelete': 117, 'end': 119, 'pagedown': 121,
    'left': 123, 'right': 124, 'down': 125, 'up': 126,
    'f1': 122, 'f2': 120, 'f3': 99, 'f4': 118, 'f5': 96, 'f6': 97,
    'f7': 98, 'f8': 100, 'f9': 101, 'f10': 109, 'f11': 103, 'f12': 111,
    # Alphabet
    'a': 0, 'b': 11, 'c': 8, 'd': 2, 'e': 14, 'f': 3, 'g': 5, 'h': 4,
    'i': 34, 'j': 38, 'k': 40, 'l': 37, 'm': 46, 'n': 45, 'o': 31, 'p': 35,
    'q': 12, 'r': 15, 's': 1, 't': 17, 'u': 32, 'v': 9, 'w': 13, 'x': 7,
    'y': 16, 'z': 6,
    # Digits
    '0': 29, '1': 18, '2': 19, '3': 20, '4': 21,
    '5': 23, '6': 22, '7': 26, '8': 28, '9': 25,
    # Punctuation
    '-': 27, '=': 24, '[': 33, ']': 30, '\\': 42,
    ';': 41, "'": 39, ',': 43, '.': 47, '/': 44, '`': 50
}

MODIFIER_CODES = {
    'command': 55, 'cmd': 55,
    'shift': 56,
    'option': 58, 'alt': 58,
    'control': 59, 'ctrl': 59,
}


class FailsafeTriggered(Exception):
    """Raised when emergency stop failsafe is activated (mouse moved to screen corner)."""
    pass


class MacOSController:
    """Controls mouse and keyboard via macOS CoreGraphics."""

    def __init__(self, failsafe=True):
        self.failsafe = failsafe
        self._screen_w, self._screen_h = self.get_screen_size()

    def get_screen_size(self):
        """Returns logical screen width and height in points."""
        disp = cg.CGMainDisplayID()
        w = cg.CGDisplayPixelsWide(disp)
        h = cg.CGDisplayPixelsHigh(disp)
        self._screen_w = w
        self._screen_h = h
        return w, h

    def get_mouse_position(self):
        """Returns current mouse (x, y) in logical coordinates."""
        evt = cg.CGEventCreate(None)
        if not evt:
            return 0.0, 0.0
        loc = cg.CGEventGetLocation(evt)
        return float(loc.x), float(loc.y)

    def check_failsafe(self):
        """Checks if mouse is in any of the four corners of the screen."""
        if not self.failsafe:
            return
        x, y = self.get_mouse_position()
        w, h = self._screen_w, self._screen_h
        corner_margin = 8
        in_top_left = (x <= corner_margin and y <= corner_margin)
        in_top_right = (x >= w - corner_margin and y <= corner_margin)
        in_bottom_left = (x <= corner_margin and y >= h - corner_margin)
        in_bottom_right = (x >= w - corner_margin and y >= h - corner_margin)

        if in_top_left or in_top_right or in_bottom_left or in_bottom_right:
            raise FailsafeTriggered(
                f"Emergency Stop! Mouse moved to screen corner ({int(x)}, {int(y)}). Aborting actions."
            )

    def move_to(self, target_x, target_y, duration=0.25, steps=12):
        """Smoothly moves mouse to (target_x, target_y)."""
        self.check_failsafe()
        start_x, start_y = self.get_mouse_position()

        # Clamp target coordinates to screen bounds
        target_x = max(0, min(self._screen_w - 1, target_x))
        target_y = max(0, min(self._screen_h - 1, target_y))

        if steps <= 1 or duration <= 0:
            pt = CGPoint(target_x, target_y)
            evt = cg.CGEventCreateMouseEvent(None, kCGEventMouseMoved, pt, 0)
            cg.CGEventPost(kCGHIDEventTap, evt)
            return

        for i in range(1, steps + 1):
            t = i / steps
            # Smooth cosine easing
            eased_t = (1.0 - math.cos(t * math.pi)) / 2.0
            cur_x = start_x + (target_x - start_x) * eased_t
            cur_y = start_y + (target_y - start_y) * eased_t

            pt = CGPoint(cur_x, cur_y)
            evt = cg.CGEventCreateMouseEvent(None, kCGEventMouseMoved, pt, 0)
            cg.CGEventPost(kCGHIDEventTap, evt)
            time.sleep(duration / steps)

        self.check_failsafe()

    def click(self, x=None, y=None, button='left', clicks=1):
        """Clicks at (x, y) or current position."""
        self.check_failsafe()
        if x is not None and y is not None:
            self.move_to(x, y, duration=0.2)
        else:
            x, y = self.get_mouse_position()

        pt = CGPoint(x, y)
        is_left = (button.lower() == 'left')
        down_type = kCGEventLeftMouseDown if is_left else kCGEventRightMouseDown
        up_type = kCGEventLeftMouseUp if is_left else kCGEventRightMouseUp
        btn_type = kCGMouseButtonLeft if is_left else kCGMouseButtonRight

        for click_idx in range(1, clicks + 1):
            # Mouse Down
            evt_down = cg.CGEventCreateMouseEvent(None, down_type, pt, btn_type)
            cg.CGEventSetIntegerValueField(evt_down, kCGMouseEventClickState, click_idx)
            cg.CGEventPost(kCGHIDEventTap, evt_down)
            time.sleep(0.05)

            # Mouse Up
            evt_up = cg.CGEventCreateMouseEvent(None, up_type, pt, btn_type)
            cg.CGEventSetIntegerValueField(evt_up, kCGMouseEventClickState, click_idx)
            cg.CGEventPost(kCGHIDEventTap, evt_up)
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
        pt_start = CGPoint(start_x, start_y)

        # Mouse Down
        evt_down = cg.CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, pt_start, kCGMouseButtonLeft)
        cg.CGEventPost(kCGHIDEventTap, evt_down)
        time.sleep(0.1)

        # Drag loop
        for i in range(1, steps + 1):
            t = i / steps
            eased_t = (1.0 - math.cos(t * math.pi)) / 2.0
            cur_x = start_x + (end_x - start_x) * eased_t
            cur_y = start_y + (end_y - start_y) * eased_t
            pt = CGPoint(cur_x, cur_y)
            evt_drag = cg.CGEventCreateMouseEvent(None, kCGEventLeftMouseDragged, pt, kCGMouseButtonLeft)
            cg.CGEventPost(kCGHIDEventTap, evt_drag)
            time.sleep(duration / steps)

        # Mouse Up
        pt_end = CGPoint(end_x, end_y)
        evt_up = cg.CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, pt_end, kCGMouseButtonLeft)
        cg.CGEventPost(kCGHIDEventTap, evt_up)
        time.sleep(0.1)
        self.check_failsafe()

    def scroll(self, clicks=5, direction='down'):
        """Scrolls the mouse wheel. direction can be 'up', 'down', 'left', 'right'."""
        self.check_failsafe()
        # In CoreGraphics: positive dy scrolls up, negative dy scrolls down
        val = int(clicks)
        if direction.lower() == 'down':
            dy = -val
        elif direction.lower() == 'up':
            dy = val
        else:
            dy = -val

        for _ in range(abs(val)):
            step = 1 if dy > 0 else -1
            evt = cg.CGEventCreateScrollWheelEvent(None, 0, 1, step * 4)
            cg.CGEventPost(kCGHIDEventTap, evt)
            time.sleep(0.02)

    def type_text(self, text, press_enter_after=False):
        """Types unicode string into the currently focused window."""
        self.check_failsafe()
        for char in text:
            # Create dummy keyboard event and attach unicode character
            evt_down = cg.CGEventCreateKeyboardEvent(None, 0, True)
            cg.CGEventKeyboardSetUnicodeString(evt_down, 1, char)
            cg.CGEventPost(kCGHIDEventTap, evt_down)

            evt_up = cg.CGEventCreateKeyboardEvent(None, 0, False)
            cg.CGEventKeyboardSetUnicodeString(evt_up, 1, char)
            cg.CGEventPost(kCGHIDEventTap, evt_up)

            time.sleep(0.015)

        if press_enter_after:
            time.sleep(0.05)
            self.press_key('return')

    def press_key(self, key_name):
        """Presses a single key by name (e.g. 'return', 'tab', 'escape', 'space')."""
        self.check_failsafe()
        name = key_name.lower().strip()
        code = KEY_CODES.get(name)
        if code is None:
            # Fallback: type as unicode character if 1 char
            if len(key_name) == 1:
                self.type_text(key_name)
                return
            raise ValueError(f"Unknown key: {key_name}")

        evt_down = cg.CGEventCreateKeyboardEvent(None, code, True)
        cg.CGEventPost(kCGHIDEventTap, evt_down)
        time.sleep(0.05)

        evt_up = cg.CGEventCreateKeyboardEvent(None, code, False)
        cg.CGEventPost(kCGHIDEventTap, evt_up)
        time.sleep(0.05)

    def hotkey(self, keys):
        """Executes a key combination, e.g. ['command', 'space'] or ['cmd', 'c']."""
        self.check_failsafe()
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split('+')]

        modifier_codes = []
        regular_keys = []

        for k in keys:
            k_low = k.lower().strip()
            if k_low in MODIFIER_CODES:
                modifier_codes.append(MODIFIER_CODES[k_low])
            elif k_low in KEY_CODES:
                regular_keys.append(KEY_CODES[k_low])
            else:
                raise ValueError(f"Unknown key in hotkey combo: {k}")

        # Press modifiers down
        for mod_code in modifier_codes:
            evt = cg.CGEventCreateKeyboardEvent(None, mod_code, True)
            cg.CGEventPost(kCGHIDEventTap, evt)
            time.sleep(0.02)

        # Press regular keys
        for key_code in regular_keys:
            evt_down = cg.CGEventCreateKeyboardEvent(None, key_code, True)
            cg.CGEventPost(kCGHIDEventTap, evt_down)
            time.sleep(0.03)

            evt_up = cg.CGEventCreateKeyboardEvent(None, key_code, False)
            cg.CGEventPost(kCGHIDEventTap, evt_up)
            time.sleep(0.02)

        # Release modifiers in reverse order
        for mod_code in reversed(modifier_codes):
            evt = cg.CGEventCreateKeyboardEvent(None, mod_code, False)
            cg.CGEventPost(kCGHIDEventTap, evt)
            time.sleep(0.02)

        time.sleep(0.05)
