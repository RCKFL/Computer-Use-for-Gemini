"""Diagnostic check for Windows environment and Gemini API.
"""

import sys
import os
import urllib.request
import ssl


def main():
    print("=" * 60)
    print("      Gemini Computer Use - Windows Diagnostics & Setup      ")
    print("=" * 60)

    # 1. Platform
    print(f"\n[1] OS Platform: {sys.platform}")
    if sys.platform.startswith('win'):
        print("    ✅ Running on native Windows.")
    else:
        print(f"    ℹ️  Running on {sys.platform} (this script is designed for Windows).")

    # 2. DPI & Display
    print("\n[2] Checking Display & Win32 API...")
    try:
        import ctypes
        if hasattr(ctypes, 'windll'):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
            print(f"    ✅ Win32 user32 loaded. Primary Display: {w}x{h}")
        else:
            print("    ℹ️  ctypes.windll is only available when running on Windows.")
    except Exception as e:
        print(f"    ⚠️ Display check error: {e}")

    # 3. Pillow
    print("\n[3] Checking Pillow (Fast Screen Capture)...")
    try:
        import PIL
        print(f"    ✅ Pillow is installed (v{PIL.__version__}). Ultra-fast screen capture active.")
    except ImportError:
        print("    ℹ️  Pillow is not installed. Native Windows PowerShell capture will be used.")
        print("       (Tip: run 'install.bat' or 'pip install pillow' for maximum performance).")

    # 4. API Key & Connectivity
    print("\n[4] Checking Gemini API Key & Connection...")
    from gemini_client_windows import BUILTIN_API_KEY
    api_key = os.environ.get("GEMINI_API_KEY", "").strip() or BUILTIN_API_KEY.strip()
    
    # Also check .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not api_key and os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if k and not k.startswith("AIzaSyВаш"):
                            api_key = k
                            break
        except Exception:
            pass

    if api_key:
        masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
        print(f"    ✅ API key is configured ({masked}).")
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                print("    ✅ Connection to Google Gemini API is working!")
        except Exception as e:
            print(f"    ⚠️ API connection test note: {e}")
    else:
        print("    ℹ️  API key is not configured yet.")
        print("       Set it in run.py (GEMINI_API_KEY = \"...\") or in a .env file.")

    print("\n" + "=" * 60)
    print("Готово! Для запуска используйте run.bat или python run.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
