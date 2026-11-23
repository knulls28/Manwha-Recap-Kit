#!/usr/bin/env python3
"""
Manhwa Recap Video Creation Engine - Standalone CLI Tool
Automates end-to-end recap video creation from raw webtoon chapters (CBZ/ZIP/folders).
"""

import os
import sys
import re
import argparse
import zipfile
from pathlib import Path

# Add project root to path
WORKSPACE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from modules.preset import load_config
from modules.slicer import slice_directory
from modules.story_sync import build_synced_story_video

BANNER = r"""
╔══════════════════════════════════════════════════════════════════════════╗
║               MANHWA RECAP VIDEO CREATION ENGINE v2.0                    ║
║          High-Retention Subpixel Motion • Edge-TTS • Parallel            ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

def prompt_path(prompt_text: str, default: str = None) -> Path:
    while True:
        display_prompt = f"{prompt_text} [{default}]: " if default else f"{prompt_text}: "
        try:
            val = input(display_prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)
        if not val and default:
            val = default
        if val:
            p = Path(val).expanduser().resolve()
            return p
        print("  [!] Please enter a valid path.")

def find_chapter_file(chapters_dir: Path, chapter_num: int) -> Path | None:
    patterns = [
        f"*Chapter*{chapter_num}*.cbz",
        f"*chapter*{chapter_num}*.cbz",
        f"*ch*{chapter_num}*.cbz",
        f"*{chapter_num}*.cbz",
        f"*Chapter*{chapter_num}*.zip",
        f"*chapter*{chapter_num}*.zip",
        f"*ch*{chapter_num}*.zip",
        f"*{chapter_num}*.zip",
    ]
    for pat in patterns:
        matches = sorted(list(chapters_dir.glob(pat)))
        if matches:
            # Filter to avoid false positives (e.g. searching for 1 matching 12)
            for m in matches:
                nums = re.findall(r'\d+', m.stem)
                if str(chapter_num) in nums:
                    return m
            return matches[0]
            
    # Check for direct directory
    for p in chapters_dir.iterdir():
        if p.is_dir() and str(chapter_num) in re.findall(r'\d+', p.name):
            return p
            
    return None

def main():
    print(BANNER)
    
    parser = argparse.ArgumentParser(description="Create frame-perfect Manhwa Recap videos.")
    parser.add_argument("--chapters-dir", type=str, help="Directory containing raw chapter CBZ/ZIP files or folders")
    parser.add_argument("--project-dir", type=str, help="Directory where project files and output videos will be stored")
    parser.add_argument("--chapter", type=int, help="Chapter number to process (e.g. 8)")
    parser.add_argument("--title-hook", type=str, default="", help="Custom plot hook for video title")
    parser.add_argument("--series-title", type=str, default="Leveling Up with the Gods", help="Name of the manhwa series")
    parser.add_argument("--watermark-badge", type=str, default="", help="Path to custom watermark badge PNG")
    parser.add_argument("--voice", type=str, default="en-US-BrianNeural", help="Edge-TTS voice (default: en-US-BrianNeural)")
    parser.add_argument("--speed", type=str, default="+15%", help="Narration speed rate (default: +15%%)")
    args = parser.parse_args()

    # 1. Ask the 2 Essential Locations (or read from CLI)
    if not args.chapters_dir:
        chapters_dir = prompt_path("Enter path to raw chapters directory (CBZ/ZIP/folders)")
    else:
        chapters_dir = Path(args.chapters_dir).expanduser().resolve()

    if not chapters_dir.exists():
        print(f"[!] Error: Chapters directory not found: {chapters_dir}")
        sys.exit(1)

    if not args.project_dir:
        default_proj = str(WORKSPACE_ROOT / "Projects" / args.series_title)
        project_dir = prompt_path("Enter project output workspace directory", default=default_proj)
    else:
        project_dir = Path(args.project_dir).expanduser().resolve()

    # 2. Select Chapter Number
    if args.chapter is None:
        try:
            ch_input = input("Enter chapter number to process [1]: ").strip()
            chapter_num = int(ch_input) if ch_input else 1
        except ValueError:
            print("[!] Invalid chapter number.")
            sys.exit(1)
    else:
        chapter_num = args.chapter

    ch_tag = f"ch{chapter_num:02d}"
    print(f"\n[+] Target Chapter: {chapter_num} ({ch_tag})")
    print(f"[+] Chapters Source: {chapters_dir}")
    print(f"[+] Project Workspace: {project_dir}")

    # Setup Directory Tree
    extract_dir = project_dir / "extracted" / ch_tag
    panels_dir = project_dir / "panels" / ch_tag
    scripts_dir = project_dir / "scripts"
    audio_dir = project_dir / "audio" / ch_tag
    cache_dir = project_dir / ".scene_cache"
    output_dir = project_dir / "output" / f"Chapter {chapter_num:02d}"

    extract_dir.mkdir(parents=True, exist_ok=True)
    panels_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Chapter Extraction
    src_file = find_chapter_file(chapters_dir, chapter_num)
    if not src_file:
        print(f"[!] Warning: Could not auto-detect Chapter {chapter_num} in {chapters_dir}")
        manual = prompt_path("Please enter exact path to the chapter file/folder")
        src_file = manual

    print(f"\n[*] Extracting: {src_file.name}...")
    if src_file.suffix.lower() in [".cbz", ".zip"]:
        with zipfile.ZipFile(src_file, "r") as z:
            z.extractall(extract_dir)
    elif src_file.is_dir():
        import shutil
        for img in src_file.glob("*.*"):
            if img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                shutil.copy(img, extract_dir / img.name)
    print(f"[✓] Extracted to: {extract_dir}")

    # 4. Gutter Slicing
    existing_panels = sorted(list(panels_dir.glob("*.png")))
    if not existing_panels:
        print(f"\n[*] Slicing continuous webtoon strips at natural gutters...")
        sliced_panels = slice_directory(extract_dir, panels_dir, prefix=ch_tag)
    else:
        sliced_panels = existing_panels
        print(f"\n[✓] Found {len(sliced_panels)} pre-sliced panels in {panels_dir}")

    if not sliced_panels:
        print("[!] Error: No panels extracted or sliced.")
        sys.exit(1)

    # 5. Narration Script
    script_file = scripts_dir / f"{ch_tag}_script.txt"
    if script_file.exists():
        print(f"\n[✓] Using existing narration script: {script_file.name}")
        with open(script_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
    else:
        print(f"\n[*] Generating initial 10-scene template script at {script_file}...")
        template_lines = [
            f"{args.series_title} Chapter {chapter_num} is finally here, and the atmosphere in the dungeon is so tense you could cut it with a blade!",
            "Facing overwhelming odds, the protagonist doesn't flinch for even a second—calculating his next move with icy precision.",
            "The arrogant villains laugh in his face, completely unaware that they're dealing with someone who has seen the end of the world.",
            "A sudden system alert chimes across the screen, warning everyone that time is rapidly running out!",
            "That's when he unleashes an insane display of power, smashing through expectations and leaving the entire crowd speechless!",
            "His status window flashes with massive point deductions and a brand new hidden skill unlock!",
            "Instead of celebrating, he calmly steps through the carnage, preparing for the true nightmare that awaits in phase two.",
            "Without warning, the dungeon barrier shatters—and a terrifying horde of high-tier monsters floods the arena!",
            "The bullies who talked so much trash are instantly overrun, begging for salvation as chaos erupts!",
            f"And right in the center of the slaughter, a dark silhouette stands tall with glowing eyes ready to feast. Drop a follow for Chapter {chapter_num + 1}!"
        ]
        with open(script_file, "w", encoding="utf-8") as f:
            f.write("\n".join(template_lines) + "\n")
        lines = template_lines
        print(f"[✓] Template script written. You can edit {script_file} anytime!")

    # 6. Map Panels to Scenes
    num_scenes = len(lines)
    panels_per_scene = max(1, len(sliced_panels) // num_scenes)
    scenes = []
    for idx, text in enumerate(lines):
        start_p = idx * panels_per_scene
        end_p = min(len(sliced_panels), (idx + 1) * panels_per_scene)
        scene_panels = [str(p) for p in sliced_panels[start_p:end_p]]
        if not scene_panels:
            scene_panels = [str(sliced_panels[-1])]
        actions = ["zoom_in" if i % 2 == 0 else "scroll" for i in range(len(scene_panels))]
        scenes.append({
            "text": text,
            "panels": scene_panels,
            "actions": actions
        })

    # 7. Configure Presets & Branding
    cfg = load_config()
    cfg["tts"]["engine"] = "edge"
    cfg["tts"]["edge"]["default_voice"] = args.voice
    cfg["tts"]["edge"]["rate"] = args.speed

    cfg["video"]["formats"]["shorts"]["font_size"] = 74
    cfg["video"]["formats"]["shorts"]["margin_v"] = 480
    cfg["video"]["formats"]["shorts"]["outline_width"] = 7
    cfg["subtitles"]["words_per_cue"] = 3
    cfg["subtitles"]["uppercase"] = True

    # Watermark Badge
    badge_path = None
    if args.watermark_badge and Path(args.watermark_badge).exists():
        badge_path = Path(args.watermark_badge).resolve()
    else:
        default_badge = WORKSPACE_ROOT / "assets" / "nulls_crest_transparent.png"
        if default_badge.exists():
            badge_path = default_badge

    cfg["watermark"]["badge_width"] = 320
    cfg["watermark"]["badge_y"] = 1020
    cfg["watermark"]["opacity"] = 0.78

    # Title Hook (Option C format)
    hook = args.title_hook.strip()
    if not hook:
        hook = "The College Bullies Realize They Messed With A Monster" if chapter_num == 8 else f"The Regressor Humiliates Everyone In Stage {chapter_num}"
    final_title = f"[Ch. {chapter_num}] {hook} - {args.series_title} Recap.mp4"
    output_mp4 = output_dir / final_title
    audio_mp3 = audio_dir / f"chapter_{chapter_num:02d}_narration.mp3"
    subtitles_srt = audio_dir / f"chapter_{chapter_num:02d}_subtitles.srt"

    print(f"\n[*] Rendering video: {final_title}")
    res_path = build_synced_story_video(
        scenes=scenes,
        audio_path=audio_mp3,
        srt_path=subtitles_srt,
        output_path=output_mp4,
        preset_name="shorts",
        watermark_text=None,
        watermark_image=badge_path,
        config=cfg,
        cache_dir=cache_dir,
        end_padding=1.5,
        primary_colour="&H00FF3BE0"
    )

    print("\n" + "=" * 65)
    print(f"[✓] Video Recap Successfully Rendered!")
    print(f"    Path: {res_path}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
