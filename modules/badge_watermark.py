#!/usr/bin/env python3
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = BASE_DIR / "assets" / "fonts"

def draw_diamond(draw, cx, cy, radius, fill, outline=None, width=1):
    points = [
        (cx, cy - radius),
        (cx + radius, cy),
        (cx, cy + radius),
        (cx - radius, cy)
    ]
    draw.polygon(points, fill=fill, outline=outline, width=width)

def draw_arcane_eye_rune(draw, cx, cy, scale=1.0, color=(0, 240, 255, 255)):
    """Draws a stylized arcane eye rune with orbital wings and concentric pupils"""
    w = int(50 * scale)
    h = int(22 * scale)
    
    # Outer almond / eye arc
    draw.arc([cx - w, cy - h, cx + w, cy + h], start=20, end=160, fill=color, width=max(2, int(4 * scale)))
    draw.arc([cx - w, cy - h, cx + w, cy + h], start=200, end=340, fill=color, width=max(2, int(4 * scale)))
    
    # Orbital rings / wings on left and right
    r_wing = int(24 * scale)
    draw.ellipse([cx - w - r_wing, cy - r_wing, cx - w + r_wing, cy + r_wing], outline=color, width=max(2, int(3 * scale)))
    draw.ellipse([cx + w - r_wing, cy - r_wing, cx + w + r_wing, cy + r_wing], outline=color, width=max(2, int(3 * scale)))
    
    # Center pupil and iris
    r_iris = int(14 * scale)
    draw.ellipse([cx - r_iris, cy - r_iris, cx + r_iris, cy + r_iris], outline=color, width=max(2, int(3 * scale)))
    r_pupil = int(5 * scale)
    draw.ellipse([cx - r_pupil, cy - r_pupil, cx + r_pupil, cy + r_pupil], fill=color)

def generate_nulls_recap_badge(
    top_text: str = "NULLS",
    bottom_text: str = "RECAP",
    top_color: str = "#00F0FF",       # Electric Cyan
    bottom_color: str = "#E8ECEF",    # Crisp Silver/White
    slash_color: str = "#FFFFFF",     # Pure White Slash
    contour_fill: tuple = (22, 24, 32, 185), # Dark slate translucent backing
    border_color: tuple = (110, 115, 130, 220), # Sleek die-cut border
    border_width: int = 5,
    contour_padding: int = 28,
    scale: float = 1.0
) -> Image.Image:
    """
    Procedurally creates an ultra-crisp, die-cut vector-grade watermark badge
    with custom typography, diagonal blade slash, and rune crest accents.
    """
    canvas_w = int(700 * scale)
    canvas_h = int(450 * scale)
    
    font_path = FONTS_DIR / "Montserrat.ttf"
    if not font_path.exists():
        font_path = FONTS_DIR / "SourceSansPro-Bold.ttf"
        
    font_top = ImageFont.truetype(str(font_path), int(80 * scale))
    font_bot = ImageFont.truetype(str(font_path), int(68 * scale))
    
    # Step 1: Draw foreground mask at high resolution to calculate die-cut contour
    mask_img = Image.new("L", (canvas_w, canvas_h), 0)
    mask_draw = ImageDraw.Draw(mask_img)
    
    cx = canvas_w // 2
    top_y = int(130 * scale)
    bot_y = int(225 * scale)
    rune_y = int(75 * scale)
    
    # Top Rune
    draw_arcane_eye_rune(mask_draw, cx, rune_y, scale=scale * 1.0, color=255)
    
    # Top Text: NULLS
    bbox_top = mask_draw.textbbox((0, 0), top_text, font=font_top)
    w_top = bbox_top[2] - bbox_top[0]
    mask_draw.text((cx - w_top // 2, top_y), top_text, font=font_top, fill=255)
    
    # Bottom Text: RECAP
    bbox_bot = mask_draw.textbbox((0, 0), bottom_text, font=font_bot)
    w_bot = bbox_bot[2] - bbox_bot[0]
    mask_draw.text((cx - w_bot // 2, bot_y), bottom_text, font=font_bot, fill=255)
    
    # Left & Right Flanking Diamonds
    diamond_r = int(14 * scale)
    draw_diamond(mask_draw, cx - w_top // 2 - int(45 * scale), top_y + int(45 * scale), diamond_r, fill=255)
    draw_diamond(mask_draw, cx + w_top // 2 + int(45 * scale), top_y + int(45 * scale), diamond_r, fill=255)
    
    # Bottom Diamond Anchor
    draw_diamond(mask_draw, cx, bot_y + int(85 * scale), int(12 * scale), fill=255)
    draw_diamond(mask_draw, cx, bot_y + int(105 * scale), int(7 * scale), fill=255)
    
    # Center Blade Slash
    slash_y = top_y + int(85 * scale)
    slash_poly = [
        (cx - int(190 * scale), slash_y + int(12 * scale)),
        (cx - int(30 * scale), slash_y + int(4 * scale)),
        (cx + int(190 * scale), slash_y - int(12 * scale)),
        (cx + int(20 * scale), slash_y - int(2 * scale))
    ]
    mask_draw.polygon(slash_poly, fill=255)
    
    # Step 2: Expand mask to create die-cut contour backing
    pad_kernel = contour_padding * 2 + 1
    expanded_mask = mask_img.filter(ImageFilter.MaxFilter(pad_kernel))
    # Smooth the contour edges
    smoothed_mask = expanded_mask.filter(ImageFilter.GaussianBlur(radius=int(4 * scale)))
    smoothed_mask = smoothed_mask.point(lambda p: 255 if p > 120 else 0)
    
    # Step 3: Draw Outer Contour Border
    border_kernel = border_width * 2 + 1
    border_mask = smoothed_mask.filter(ImageFilter.MaxFilter(border_kernel))
    # Border is area between border_mask and smoothed_mask
    
    # Step 4: Assemble Final RGBA Image
    badge = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge)
    
    # Draw border outline
    border_layer = Image.new("RGBA", (canvas_w, canvas_h), border_color)
    border_diff = Image.new("L", (canvas_w, canvas_h), 0)
    b_arr = border_mask.load()
    s_arr = smoothed_mask.load()
    d_arr = border_diff.load()
    for y in range(canvas_h):
        for x in range(canvas_w):
            if b_arr[x, y] > 0 and s_arr[x, y] == 0:
                d_arr[x, y] = 255
    border_layer.putalpha(border_diff)
    badge = Image.alpha_composite(badge, border_layer)
    
    # Draw contour background fill
    bg_layer = Image.new("RGBA", (canvas_w, canvas_h), contour_fill)
    bg_layer.putalpha(smoothed_mask)
    badge = Image.alpha_composite(badge, bg_layer)
    
    # Draw crisp foreground elements
    fg = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    fg_draw = ImageDraw.Draw(fg)
    
    # Rune in Top Color
    draw_arcane_eye_rune(fg_draw, cx, rune_y, scale=scale * 1.0, color=top_color)
    
    # Flanking Diamonds
    draw_diamond(fg_draw, cx - w_top // 2 - int(45 * scale), top_y + int(45 * scale), diamond_r, fill=top_color)
    draw_diamond(fg_draw, cx + w_top // 2 + int(45 * scale), top_y + int(45 * scale), diamond_r, fill=top_color)
    draw_diamond(fg_draw, cx, bot_y + int(85 * scale), int(12 * scale), fill=top_color)
    draw_diamond(fg_draw, cx, bot_y + int(105 * scale), int(7 * scale), fill=top_color)
    
    # Top Text
    fg_draw.text((cx - w_top // 2, top_y), top_text, font=font_top, fill=top_color)
    
    # Bottom Text
    fg_draw.text((cx - w_bot // 2, bot_y), bottom_text, font=font_bot, fill=bottom_color)
    
    # Blade Slash
    fg_draw.polygon(slash_poly, fill=slash_color)
    
    # Composite foreground
    badge = Image.alpha_composite(badge, fg)
    
    # Crop to content bounding box
    bbox = badge.getbbox()
    if bbox:
        # Add 10px margin
        pad = int(10 * scale)
        crop_box = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(canvas_w, bbox[2] + pad),
            min(canvas_h, bbox[3] + pad)
        )
        badge = badge.crop(crop_box)
        
    return badge

if __name__ == "__main__":
    out_dir = BASE_DIR / "assets"
    # Variant 1: Electric Cyan & Silver (Reference match)
    badge_cyan = generate_nulls_recap_badge(top_color="#00F0FF", bottom_color="#FFFFFF", slash_color="#FFFFFF")
    badge_cyan.save(out_dir / "nulls_recap_badge_cyan.png", "PNG")
    print(f"[✓] Generated {out_dir / 'nulls_recap_badge_cyan.png'} ({badge_cyan.size})")
    
    # Variant 2: Neon Magenta & Electric Violet (TikTok palette match)
    badge_magenta = generate_nulls_recap_badge(top_color="#FF2DF0", bottom_color="#FFFFFF", slash_color="#00F0FF")
    badge_magenta.save(out_dir / "nulls_recap_badge_magenta.png", "PNG")
    print(f"[✓] Generated {out_dir / 'nulls_recap_badge_magenta.png'} ({badge_magenta.size})")
    
    # Variant 3: Radiant Gold & Ice Cyan (Cinder Eyes theme)
    badge_gold = generate_nulls_recap_badge(top_color="#FFD700", bottom_color="#FFFFFF", slash_color="#00F0FF")
    badge_gold.save(out_dir / "nulls_recap_badge_gold.png", "PNG")
    print(f"[✓] Generated {out_dir / 'nulls_recap_badge_gold.png'} ({badge_gold.size})")
