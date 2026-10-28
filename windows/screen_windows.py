"""Windows Screen Capture and Coordinate Conversion for Gemini Computer Use.

Supports:
1. Fast in-memory capture via Pillow (if installed).
2. Native PowerShell System.Drawing fallback (built into Windows, zero dependencies).
3. Automatic 0..1000 normalized coordinate mapping.
"""

import sys
import os
import io
import base64
import tempfile
import subprocess

is_windows = sys.platform.startswith('win')

# Check if PIL is available
try:
    from PIL import ImageGrab, Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class WindowsScreenManager:
    """Handles taking screenshots on Windows and coordinate conversion."""

    def __init__(self, target_max_dimension=1280, jpeg_quality=80):
        self.target_max_dimension = target_max_dimension
        self.jpeg_quality = jpeg_quality
        self.width, self.height = self.get_screen_dimensions()

    def get_screen_dimensions(self):
        """Returns the primary screen width and height in pixels."""
        if is_windows:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
            return w, h
        return 1920, 1080

    def capture(self, output_path=None):
        """Captures the screen and returns base64-encoded JPEG image data.

        Returns:
            dict containing:
                - 'base64': base64-encoded JPEG string
                - 'width': screen width
                - 'height': screen height
                - 'mime_type': 'image/jpeg'
        """
        self.width, self.height = self.get_screen_dimensions()

        # Method 1: Using Pillow (Fastest)
        if HAS_PIL:
            try:
                img = ImageGrab.grab()
                # Downscale if needed
                w, h = img.size
                self.width, self.height = w, h
                if max(w, h) > self.target_max_dimension:
                    ratio = self.target_max_dimension / float(max(w, h))
                    new_w = int(w * ratio)
                    new_h = int(h * ratio)
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Convert to RGB if necessary (e.g. RGBA)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=self.jpeg_quality)
                b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

                if output_path:
                    with open(output_path, 'wb') as f:
                        f.write(buffer.getvalue())

                return {
                    'base64': b64_str,
                    'width': self.width,
                    'height': self.height,
                    'mime_type': 'image/jpeg'
                }
            except Exception as e:
                # Fallback to PowerShell
                pass

        # Method 2: Native PowerShell (Zero pip dependencies on Windows)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_jpg = tmp.name

        try:
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                "$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
                "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
                "$graphics.CopyFromScreen(0, 0, 0, 0, $bitmap.Size); "
                f"$bitmap.Save('{tmp_jpg}', [System.Drawing.Imaging.ImageFormat]::Jpeg); "
                "$graphics.Dispose(); "
                "$bitmap.Dispose();"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True
            )
            if res.returncode != 0:
                raise RuntimeError(f"PowerShell screen capture failed: {res.stderr}")

            with open(tmp_jpg, 'rb') as f:
                img_data = f.read()
                b64_str = base64.b64encode(img_data).decode('utf-8')

            return {
                'base64': b64_str,
                'width': self.width,
                'height': self.height,
                'mime_type': 'image/jpeg'
            }
        finally:
            if os.path.exists(tmp_jpg):
                try:
                    os.remove(tmp_jpg)
                except Exception:
                    pass

    def normalized_to_pixel(self, norm_x, norm_y):
        """Converts normalized (0..1000) coordinates to screen pixels (x, y)."""
        clamped_x = max(0.0, min(1000.0, float(norm_x)))
        clamped_y = max(0.0, min(1000.0, float(norm_y)))

        px_x = int((clamped_x / 1000.0) * self.width)
        px_y = int((clamped_y / 1000.0) * self.height)

        return px_x, px_y
