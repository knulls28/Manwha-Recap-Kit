import os
import glob
from pathlib import Path
from PIL import Image
import numpy as np

def find_gutters(img_gray: Image.Image, min_gutter_height: int = 20, variance_threshold: float = 4.0) -> list[int]:
    """
    Finds horizontal cut points (gutters/whitespace) between webtoon panels.
    Detects contiguous bands of near-uniform pixels (low variance).
    """
    arr = np.array(img_gray)
    height, width = arr.shape
    
    # Calculate row-level standard deviation (uniform color rows have near-zero std)
    row_stds = np.std(arr, axis=1)
    is_gutter_row = row_stds < variance_threshold
    
    cut_points = []
    in_gutter = False
    gutter_start = 0
    
    for y in range(height):
        if is_gutter_row[y]:
            if not in_gutter:
                in_gutter = True
                gutter_start = y
        else:
            if in_gutter:
                gutter_len = y - gutter_start
                if gutter_len >= min_gutter_height:
                    cut_points.append((gutter_start + y) // 2)
                in_gutter = False
                
    if in_gutter and (height - gutter_start) >= min_gutter_height:
        cut_points.append((gutter_start + height) // 2)
        
    return cut_points

def clean_trim_panel(img: Image.Image, min_height: int = 120, variance_threshold: float = 4.0) -> Image.Image | None:
    """
    Trims excessive blank borders from top and bottom of a panel.
    Returns None if panel is completely empty or smaller than min_height.
    """
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    if h < min_height:
        return None
        
    row_stds = np.std(arr, axis=1)
    non_blank_rows = np.where(row_stds >= variance_threshold)[0]
    
    if len(non_blank_rows) == 0:
        return None
        
    top = max(0, non_blank_rows[0] - 5)
    bottom = min(h, non_blank_rows[-1] + 5)
    
    if (bottom - top) < min_height:
        return None
        
    return img.crop((0, top, w, bottom))

def slice_strip_clean(
    image_path: Path,
    output_dir: Path,
    prefix: str,
    start_index: int = 1,
    min_panel_height: int = 150
) -> int:
    """
    Cleanly slices a webtoon strip at true gutters only.
    Does NOT arbitrarily chop or create overlapping duplicate cuts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as raw_img:
        img = raw_img.convert("RGB")
        width, height = img.size
        
        # If image is standard aspect ratio (< 1.6), it is already a single panel
        if height / width < 1.6:
            trimmed = clean_trim_panel(img, min_height=min_panel_height)
            if trimmed:
                out_name = f"{prefix}_{start_index:04d}.png"
                trimmed.save(output_dir / out_name, "PNG", quality=95)
                return start_index + 1
            return start_index
            
        # Detect gutters on grayscale
        gray = img.convert("L")
        cuts = find_gutters(gray)
        all_cuts = sorted(list(set([0] + cuts + [height])))
        
        current_idx = start_index
        for i in range(len(all_cuts) - 1):
            y_top = all_cuts[i]
            y_bottom = all_cuts[i + 1]
            panel_h = y_bottom - y_top
            
            if panel_h < min_panel_height:
                continue
                
            panel = img.crop((0, y_top, width, y_bottom))
            trimmed = clean_trim_panel(panel, min_height=min_panel_height)
            
            if trimmed:
                out_name = f"{prefix}_{current_idx:04d}.png"
                trimmed.save(output_dir / out_name, "PNG", quality=95)
                current_idx += 1
                
        return current_idx

def slice_directory(input_dir: str | Path, output_dir: str | Path, prefix: str = "panel") -> list[Path]:
    """
    Processes all webtoon strip files in input_dir and cleanly slices them into output_dir.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    extensions = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    image_files = []
    for ext in extensions:
        image_files.extend(input_path.glob(ext))
    image_files = sorted(image_files)
    
    if not image_files:
        print(f"[!] No images found in {input_path}")
        return []
        
    print(f"[*] Found {len(image_files)} source strips to slice in {input_path.name}")
    next_idx = 1
    for f in image_files:
        next_idx = slice_strip_clean(f, output_path, prefix=prefix, start_index=next_idx)
        
    sliced_panels = sorted(list(output_path.glob("*.png")))
    print(f"[+] Slicing complete! Extracted {len(sliced_panels)} clean, non-overlapping panels to {output_path.name}")
    return sliced_panels
