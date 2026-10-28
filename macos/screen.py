"""macOS Screen Capture and Coordinate Conversion for Gemini Computer Use.

Uses macOS built-in `screencapture` and `sips` for hardware-accelerated,
zero-dependency screen capture and optimization.
"""

import os
import subprocess
import base64
import tempfile
import ctypes

cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
cg.CGMainDisplayID.restype = ctypes.c_uint32
cg.CGDisplayPixelsWide.restype = ctypes.c_size_t
cg.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]
cg.CGDisplayPixelsHigh.restype = ctypes.c_size_t
cg.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]


class ScreenManager:
    """Handles taking screenshots, image resizing, and coordinate mapping."""

    def __init__(self, target_max_dimension=1280, jpeg_quality=80):
        self.target_max_dimension = target_max_dimension
        self.jpeg_quality = jpeg_quality
        self.logical_w, self.logical_h = self.get_logical_dimensions()
        self.scale_factor = self._detect_scale_factor()

    def get_logical_dimensions(self):
        """Returns the logical width and height of the main screen."""
        disp = cg.CGMainDisplayID()
        w = int(cg.CGDisplayPixelsWide(disp))
        h = int(cg.CGDisplayPixelsHigh(disp))
        return w, h

    def _detect_scale_factor(self):
        """Detects Retina scaling factor by taking a quick probe."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            res = subprocess.run(['screencapture', '-x', tmp_path], capture_output=True)
            if res.returncode == 0 and os.path.exists(tmp_path):
                sips_res = subprocess.run(
                    ['sips', '-g', 'pixelWidth', tmp_path],
                    capture_output=True,
                    text=True
                )
                for line in sips_res.stdout.splitlines():
                    if 'pixelWidth:' in line:
                        phys_w = float(line.split()[-1])
                        factor = phys_w / self.logical_w
                        return round(factor, 2)
        except Exception:
            pass
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return 2.0  # Default Mac Retina fallback

    def capture(self, output_path=None):
        """Captures the current screen and converts it to optimized JPEG.

        Returns:
            dict containing:
                - 'path': path to saved image file
                - 'base64': base64-encoded JPEG data
                - 'mime_type': 'image/jpeg'
                - 'logical_w': logical screen width
                - 'logical_h': logical screen height
                - 'scale_factor': Retina scale factor
        """
        self.logical_w, self.logical_h = self.get_logical_dimensions()

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_raw:
            raw_path = tmp_raw.name

        if output_path is None:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_out:
                final_path = tmp_out.name
        else:
            final_path = output_path

        try:
            # 1. Capture raw full screen
            cap_res = subprocess.run(
                ['screencapture', '-x', raw_path],
                capture_output=True,
                text=True
            )
            if cap_res.returncode != 0:
                raise RuntimeError(
                    f"screencapture failed: {cap_res.stderr.strip()}. Check Screen Recording permission in macOS System Settings."
                )

            # 2. Optimize & resize with sips
            sips_res = subprocess.run(
                [
                    'sips',
                    '-s', 'format', 'jpeg',
                    '-s', 'formatOptions', str(self.jpeg_quality),
                    '-Z', str(self.target_max_dimension),
                    raw_path,
                    '--out', final_path
                ],
                capture_output=True,
                text=True
            )
            if sips_res.returncode != 0:
                raise RuntimeError(f"sips conversion failed: {sips_res.stderr.strip()}")

            # 3. Read image bytes and encode to base64
            with open(final_path, 'rb') as f:
                img_bytes = f.read()
                b64_str = base64.b64encode(img_bytes).decode('utf-8')

            return {
                'path': final_path,
                'base64': b64_str,
                'mime_type': 'image/jpeg',
                'logical_w': self.logical_w,
                'logical_h': self.logical_h,
                'scale_factor': self.scale_factor
            }

        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

    def normalized_to_logical(self, norm_x, norm_y):
        """Converts normalized 0..1000 coordinates to logical screen points (x, y).

        Gemini models use [0..1000] coordinate space:
          (0, 0) is top-left
          (1000, 1000) is bottom-right
        """
        # Ensure values are within [0, 1000]
        clamped_x = max(0.0, min(1000.0, float(norm_x)))
        clamped_y = max(0.0, min(1000.0, float(norm_y)))

        log_x = (clamped_x / 1000.0) * self.logical_w
        log_y = (clamped_y / 1000.0) * self.logical_h

        return round(log_x, 1), round(log_y, 1)

    def logical_to_normalized(self, log_x, log_y):
        """Converts logical screen points to normalized 0..1000 coordinates."""
        norm_x = (float(log_x) / self.logical_w) * 1000.0
        norm_y = (float(log_y) / self.logical_h) * 1000.0
        return round(norm_x, 1), round(norm_y, 1)
