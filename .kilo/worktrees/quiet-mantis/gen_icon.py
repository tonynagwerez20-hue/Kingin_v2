"""
gen_icon.py — ITS Icon Generator
=================================
Generates its_icon.ico used by the desktop shortcut and launcher.
Run once during install:  python gen_icon.py
Requires: pip install Pillow
"""

import os
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_icon():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("ERROR: Pillow not installed. Run: pip install Pillow")
        return

    SIZE = 512
    img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    d    = ImageDraw.Draw(img)

    # ── Rounded rect background ─────────────────────────────────────────────
    R = 80
    d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=(10, 10, 10, 255))

    # ── Accent border ring ──────────────────────────────────────────────────
    d.rounded_rectangle([8, 8, SIZE - 9, SIZE - 9], radius=76,
                        outline=(0, 200, 240, 80), width=3)

    # ── Glowing circle background for chart area ────────────────────────────
    cx, cy, cr = 256, 220, 155
    for i in range(6):
        alpha = 20 - i * 3
        d.ellipse([cx - cr - i*2, cy - cr - i*2, cx + cr + i*2, cy + cr + i*2],
                  fill=(0, 200, 240, max(alpha, 4)))
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(18, 18, 30, 255))

    # ── Candlestick chart (5 candles) ───────────────────────────────────────
    # Each: (center_x, high_y, low_y, open_y, close_y, is_bullish)
    candles = [
        (145, 185, 300, 270, 215, True),
        (195, 200, 310, 285, 220, True),
        (245, 220, 330, 310, 235, True),
        (295, 195, 295, 275, 210, True),
        (345, 175, 280, 255, 190, True),
    ]
    for (cx_, hy, ly, oy, cy_, bull) in candles:
        col = (0, 232, 122, 255) if bull else (255, 45, 78, 255)
        d.line([(cx_, hy), (cx_, ly)], fill=col, width=3)
        y1, y2 = (cy_, oy) if bull else (oy, cy_)
        d.rectangle([cx_ - 14, y1, cx_ + 14, y2], fill=col)

    # ── Trend line overlay ──────────────────────────────────────────────────
    pts = [(130, 295), (180, 275), (230, 255), (280, 230), (365, 195)]
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=(0, 200, 240, 160), width=2)

    # ── Green status dot ────────────────────────────────────────────────────
    d.ellipse([440, 38, 468, 66], fill=(0, 232, 122, 255))

    # ── ITS logotype ────────────────────────────────────────────────────────
    try:
        font_big = ImageFont.truetype("arialbd.ttf", 88)
        font_sub = ImageFont.truetype("arial.ttf",   22)
    except IOError:
        try:
            font_big = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 88)
            font_sub = ImageFont.truetype("C:/Windows/Fonts/arial.ttf",   22)
        except IOError:
            font_big = ImageFont.load_default()
            font_sub = ImageFont.load_default()

    # Shadow
    d.text((258, 425), "ITS", font=font_big, fill=(0, 100, 120, 180), anchor="mt")
    # Main
    d.text((256, 423), "ITS", font=font_big, fill=(0, 200, 240, 255), anchor="mt")
    # Subtitle
    d.text((256, 492), "INSTITUTIONAL TRADING SYSTEM", font=font_sub,
           fill=(90, 120, 140, 200), anchor="mb")

    # ── Save PNG + ICO ──────────────────────────────────────────────────────
    png_path = os.path.join(BASE_DIR, "its_icon.png")
    ico_path = os.path.join(BASE_DIR, "its_icon.ico")
    img.save(png_path, "PNG")
    img.save(ico_path, format="ICO",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"[OK] Icon saved: {ico_path}")


if __name__ == "__main__":
    generate_icon()
