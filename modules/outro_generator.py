from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def generate_outro_card(output_path: Path, width: int = 1080, height: int = 1920, channel_name: str = "NULLS RECAP"):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=(12, 16, 26))
    draw = ImageDraw.Draw(img)
    
    # Outer accent border
    draw.rectangle([40, 40, width - 40, height - 40], outline=(80, 130, 255), width=6)
    draw.rectangle([55, 55, width - 55, height - 55], outline=(30, 40, 65), width=2)
    
    # Load Anton or bold font
    font_path_anton = Path("assets/fonts/Anton-Regular.ttf")
    font_path_bold = Path("assets/fonts/SourceSansPro-Bold.ttf")
    
    font_title = ImageFont.truetype(str(font_path_anton), 72)
    font_sub = ImageFont.truetype(str(font_path_anton), 90)
    font_body = ImageFont.truetype(str(font_path_bold), 36)
    font_cta = ImageFont.truetype(str(font_path_anton), 44)
    
    cx = width // 2
    
    # Top text
    draw.text((cx, 380), "THANKS FOR WATCHING", fill=(255, 230, 0), font=font_title, anchor="mm")
    
    # Center Brand Card
    card_w, card_h = 920, 520
    cy = height // 2 - 50
    draw.rectangle([cx - card_w//2, cy - card_h//2, cx + card_w//2, cy + card_h//2], fill=(20, 26, 42), outline=(80, 140, 255), width=4)
    
    # Brand Name inside Card
    draw.text((cx, cy - 120), channel_name, fill=(255, 255, 255), font=font_sub, anchor="mm")
    draw.text((cx, cy - 20), "LEVELING UP WITH THE GODS", fill=(100, 180, 255), font=font_body, anchor="mm")
    draw.text((cx, cy + 50), "CHAPTER 1 & 2 RECAP COMPLETE", fill=(180, 190, 215), font=font_body, anchor="mm")
    
    # Call to action button
    btn_w, btn_h = 820, 110
    btn_y = cy + 160
    draw.rectangle([cx - btn_w//2, btn_y - btn_h//2, cx + btn_w//2, btn_y + btn_h//2], fill=(220, 30, 50), outline=(255, 100, 100), width=3)
    draw.text((cx, btn_y), "LIKE & SUBSCRIBE FOR CHAPTER 3", fill=(255, 255, 255), font=font_cta, anchor="mm")
    
    # Bottom Tagline
    draw.text((cx, height - 320), "MORE RECAPS COMING EVERY DAY", fill=(130, 145, 175), font=font_body, anchor="mm")
    
    img.save(output_path, "JPEG", quality=95)
    print(f"[+] Outro card generated: {output_path}")

if __name__ == "__main__":
    generate_outro_card(Path("assets/outro_card.jpg"))
