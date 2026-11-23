from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance

def format_panel_cinematic(
    panel_path: Path,
    output_path: Path,
    target_width: int = 1920,
    target_height: int = 1080,
    blur_radius: int = 25,
    darken_factor: float = 0.55
) -> Path:
    """
    Transforms a manhwa panel into a professional cinematic frame:
    - Background: Blurred, darkened version of the panel filling target aspect ratio.
    - Foreground: Sharp original panel centered and scaled to fit cleanly.
    """
    with Image.open(panel_path) as raw_img:
        img = raw_img.convert("RGBA")
        pw, ph = img.size

        # 1. Create Background (fill and crop to target resolution)
        scale_bg = max(target_width / pw, target_height / ph)
        bg_w, bg_h = int(pw * scale_bg), int(ph * scale_bg)
        bg = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        
        # Center crop background
        left = (bg_w - target_width) // 2
        top = (bg_h - target_height) // 2
        bg = bg.crop((left, top, left + target_width, top + target_height))
        
        # Apply Gaussian blur
        bg = bg.filter(ImageFilter.GaussianBlur(blur_radius))
        
        # Darken background for high contrast with foreground
        enhancer = ImageEnhance.Brightness(bg.convert("RGB"))
        bg_dark = enhancer.enhance(darken_factor).convert("RGBA")
        
        # 2. Scale foreground panel to fit comfortably within 92% of target frame
        max_fg_w = int(target_width * 0.92)
        max_fg_h = int(target_height * 0.92)
        scale_fg = min(max_fg_w / pw, max_fg_h / ph)
        fg_w, fg_h = int(pw * scale_fg), int(ph * scale_fg)
        fg = img.resize((fg_w, fg_h), Image.Resampling.LANCZOS)
        
        # 3. Composite foreground centered on background
        pos_x = (target_width - fg_w) // 2
        pos_y = (target_height - fg_h) // 2
        bg_dark.paste(fg, (pos_x, pos_y), fg)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_img = bg_dark.convert("RGB")
        final_img.save(output_path, "JPEG", quality=95)
        return output_path

def batch_format_panels(
    input_dir: str | Path,
    output_dir: str | Path,
    target_width: int = 1920,
    target_height: int = 1080,
    blur_radius: int = 25,
    darken_factor: float = 0.55
) -> list[Path]:
    """
    Batch formats all extracted panels in input_dir into cinematic frames in output_dir.
    """
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    panel_files = sorted(list(in_dir.glob("*.png")) + list(in_dir.glob("*.jpg")))
    formatted_paths = []
    
    for i, p in enumerate(panel_files, 1):
        out_file = out_dir / f"frame_{i:04d}.jpg"
        format_panel_cinematic(
            p,
            out_file,
            target_width=target_width,
            target_height=target_height,
            blur_radius=blur_radius,
            darken_factor=darken_factor
        )
        formatted_paths.append(out_file)
        
    print(f"[+] Formatted {len(formatted_paths)} frames ({target_width}x{target_height}) in {out_dir}")
    return formatted_paths
