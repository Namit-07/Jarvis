# Generate a Jarvis arc reactor icon
from PIL import Image, ImageDraw, ImageFont
import os
import math

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
cx, cy = SIZE // 2, SIZE // 2

# Background circle (dark)
draw.ellipse([8, 8, SIZE-8, SIZE-8], fill=(10, 10, 20, 255))

# Outer ring glow
for i in range(4):
    offset = 12 + i * 2
    alpha = 180 - i * 40
    draw.ellipse([offset, offset, SIZE-offset, SIZE-offset],
                 outline=(0, 200, 255, alpha), width=2)

# Arc reactor rings
draw.ellipse([30, 30, SIZE-30, SIZE-30], outline=(0, 212, 255, 255), width=3)
draw.ellipse([55, 55, SIZE-55, SIZE-55], outline=(0, 180, 240, 200), width=2)

# Spinning arc segments
r = 80
for i in range(3):
    start = i * 120
    draw.arc([cx-r, cy-r, cx+r, cy+r], start=start, end=start+60,
             fill=(0, 220, 255, 255), width=4)

# Inner glow
r2 = 40
draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(0, 160, 220, 200))

# Bright center
r3 = 22
draw.ellipse([cx-r3, cy-r3, cx+r3, cy+r3], fill=(100, 230, 255, 255))

# Core dot
r4 = 8
draw.ellipse([cx-r4, cy-r4, cx+r4, cy+r4], fill=(255, 255, 255, 255))

# "J" letter
try:
    font = ImageFont.truetype("arial.ttf", 14)
except Exception:
    font = ImageFont.load_default()

# Save as ICO (multiple sizes for Windows)
assets_dir = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(assets_dir, exist_ok=True)

ico_path = os.path.join(assets_dir, "jarvis_icon.ico")
png_path = os.path.join(assets_dir, "jarvis_icon.png")

# Save full-size PNG
img.save(png_path, "PNG")

# Save as ICO with multiple resolutions
sizes = [16, 32, 48, 64, 128, 256]
icons = []
for s in sizes:
    resized = img.resize((s, s), Image.LANCZOS)
    icons.append(resized)

icons[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes],
              append_images=icons[1:])

print(f"Icon saved to: {ico_path}")
print(f"PNG saved to:  {png_path}")
