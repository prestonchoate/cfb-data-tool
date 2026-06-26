# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate platform icons from icon.png (runs on any platform — requires Pillow).

Produces:
  packaging/icon.icns  (macOS)
  packaging/icon.ico   (Windows)

Usage:  python packaging/gen_icons.py
"""

from pathlib import Path

from PIL import Image

SRC = Path(__file__).resolve().parent.parent / "app" / "resources" / "icon.png"
OUT_DIR = Path(__file__).resolve().parent

img = Image.open(SRC).convert("RGBA")

# --- macOS .icns ---
icns_sizes = [16, 32, 64, 128, 256, 512]
icns_images = []
for size in icns_sizes:
    icns_images.append(img.resize((size, size), Image.LANCZOS))
    icns_images.append(img.resize((size * 2, size * 2), Image.LANCZOS))

icns_path = OUT_DIR / "icon.icns"
icns_images[0].save(icns_path, format="ICNS", append_images=icns_images[1:])
print(f"Created {icns_path}")

# --- Windows .ico ---
ico_sizes = [16, 32, 48, 64, 128, 256]
ico_images = [img.resize((s, s), Image.LANCZOS) for s in ico_sizes]

ico_path = OUT_DIR / "icon.ico"
ico_images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=ico_images[1:])
print(f"Created {ico_path}")
