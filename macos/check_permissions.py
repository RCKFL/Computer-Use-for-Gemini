"""Diagnostic tool for macOS Permissions and Gemini Computer Use Setup.

Checks:
1. Accessibility permissions (required to move mouse & send keystrokes).
2. Screen Recording permissions (required to capture screen).
3. Gemini API key availability.
4. Display resolution & Retina scaling.
"""

import sys
import os
import subprocess
import tempfile
import ctypes


def check_accessibility(prompt_if_missing=False):
    """Checks if current terminal/process has macOS Accessibility permissions."""
    try:
        app_services = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
        )
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        app_services.AXIsProcessTrusted.argtypes = []
        trusted = app_services.AXIsProcessTrusted()
        return bool(trusted)
    except Exception as e:
        print(f"[WARN] Could not query Accessibility API: {e}")
        return False


def check_screen_recording():
    """Checks if screen recording permission is active by testing screencapture."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        path = tmp.name

    try:
        res = subprocess.run(['screencapture', '-x', path], capture_output=True)
        if res.returncode != 0:
            return False, "screencapture failed with non-zero exit code"

        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            return False, "screencapture produced empty or missing file"

        # Check if sips can read dimensions
        sips_res = subprocess.run(['sips', '-g', 'pixelWidth', path], capture_output=True, text=True)
        if 'pixelWidth:' in sips_res.stdout:
            return True, "Screen recording active and working"
        return False, "sips could not read captured screenshot"
    except Exception as e:
        return False, str(e)
    finally:
        if os.path.exists(path):
            os.remove(path)


def open_settings_pane(pane_name):
    """Opens macOS System Settings directly to the desired privacy section."""
    uris = {
        "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        "screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
    }
    uri = uris.get(pane_name)
    if uri:
        subprocess.run(['open', uri])


def main():
    print("=" * 60)
    print("      Gemini Computer Use - macOS Diagnostics & Setup      ")
    print("=" * 60)

    # 1. Accessibility
    print("\n[1] Checking macOS Accessibility Permission (Универсальный доступ)...")
    has_ax = check_accessibility()
    if has_ax:
        print("    ✅ Accessibility permission is GRANTED.")
    else:
        print("    ❌ Accessibility permission is MISSING.")
        print("       To enable:")
        print("       1. Open System Settings -> Privacy & Security -> Accessibility")
        print("       2. Turn ON toggle for Terminal (or iTerm2 / VSCode / Python)")
        print("       Opening settings now...")
        open_settings_pane("accessibility")

    # 2. Screen Recording
    print("\n[2] Checking macOS Screen Recording Permission (Запись экрана)...")
    has_sr, sr_msg = check_screen_recording()
    if has_sr:
        print("    ✅ Screen Recording permission is GRANTED.")
    else:
        print(f"    ❌ Screen Recording permission is MISSING ({sr_msg}).")
        print("       To enable:")
        print("       1. Open System Settings -> Privacy & Security -> Screen Recording")
        print("       2. Turn ON toggle for Terminal (or iTerm2 / VSCode / Python)")
        print("       Opening settings now...")
        open_settings_pane("screen_recording")

    # 3. Gemini API Key
    print("\n[3] Checking Gemini API Key...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if k and not k.startswith("AIzaSyВаш"):
                            api_key = k
                        break

    if api_key:
        masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
        print(f"    ✅ GEMINI_API_KEY is found ({masked}).")
    else:
        print("    ⚠️  GEMINI_API_KEY is NOT set.")
        print("       You can get a free API key at: https://aistudio.google.com/app/apikey")
        print("       Set it via:")
        print("         export GEMINI_API_KEY='your_api_key_here'")
        print("       Or add it to a .env file in this directory.")

    # 4. Display Metrics
    print("\n[4] Detecting Display Metrics...")
    try:
        from screen import ScreenManager
        sm = ScreenManager()
        print(f"    ✅ Main Display: {sm.logical_w}x{sm.logical_h} logical points (Scale: {sm.scale_factor}x Retina)")
    except Exception as e:
        print(f"    ⚠️  Could not detect display metrics: {e}")

    print("\n" + "=" * 60)
    all_ready = has_ax and has_sr and bool(api_key)
    if all_ready:
        print("🎉 All checks passed! Gemini Computer Use is ready to run.")
        print("   Run: python3 run.py \"Open Safari and search for today's weather\"")
    else:
        print("ℹ️  Please resolve the missing items above before running.")
    print("=" * 60)


if __name__ == "__main__":
    main()
