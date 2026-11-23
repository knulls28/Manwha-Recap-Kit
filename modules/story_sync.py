
import os
import re
import shutil
import hashlib
import subprocess
import concurrent.futures
from pathlib import Path
from PIL import Image

from modules.preset import load_config, get_resolution
from modules.formatter import format_panel_cinematic
from modules.motion import get_motion_filter
from modules.narrator import generate_elevenlabs, generate_groq_tts, generate_edge, get_audio_duration, normalize_manhwa_glossary

BASE_DIR = Path(__file__).resolve().parent.parent

def shift_srt_cues(srt_path: Path, offset_seconds: float) -> list[str]:
    """
    Parses an SRT file and shifts all timestamps forward by offset_seconds.
    Returns list of shifted cue strings.
    """
    if not srt_path.exists():
        return []
        
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_text = f.read()
        
    pattern = r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)"
    matches = re.findall(pattern, srt_text, re.DOTALL)
    
    def parse_time(ts):
        h, m, s_m = ts.split(":")
        s, ms = s_m.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
        
    def fmt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        if ms >= 1000:
            s += 1
            ms = 0
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        
    shifted = []
    for m in matches:
        t_start = parse_time(m[1]) + offset_seconds
        t_end = parse_time(m[2]) + offset_seconds
        text = m[3].strip()
        shifted.append(f"{fmt_time(t_start)} --> {fmt_time(t_end)}\n{text}\n")
        
    return shifted

def render_scene_clip(
    panel_path: Path,
    output_segment: Path,
    duration: float,
    action: str = "zoom_in",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    threads: int = 2
) -> Path:
    """
    Renders an individual panel into a buttery smooth, jitter-free video segment.
    Uses high-precision subpixel box resampling to eliminate all trembling and integer-snapping jitter.
    """
    total_frames = max(1, int(round(duration * fps)))
    
    with Image.open(panel_path) as raw_img:
        pw, ph = raw_img.size
        
    # Full bleed vertical scroll if scaled height exceeds target height
    can_scroll = (ph * (width / pw)) > (height + 50)
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{width}x{height}", "-pix_fmt", "rgb24", "-r", str(fps),
        "-i", "-",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-threads", str(threads),
        "-tune", "fastdecode",
        "-pix_fmt", "yuv420p",
        "-f", "mpegts",
        str(output_segment)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    try:
        if can_scroll and action == "scroll":
            # Full-bleed smooth vertical pan down
            with Image.open(panel_path) as raw_img:
                img = raw_img.convert("RGB")
                pw, ph = img.size
                new_h = int(ph * (width / pw))
                scaled = img.resize((width, new_h), Image.Resampling.LANCZOS)
                
            max_scroll = new_h - height
            for i in range(total_frames):
                t = i / float(total_frames - 1) if total_frames > 1 else 0.0
                y0 = max_scroll * t
                frame = scaled.resize((width, height), resample=Image.Resampling.BILINEAR, box=(0.0, y0, float(width), y0 + float(height)))
                proc.stdin.write(frame.tobytes())
                
        else:
            # Standard cinematic framed panel with blurred background + subpixel Ken Burns zoom
            temp_framed = output_segment.parent / f"framed_{output_segment.stem}_{id(output_segment)}.png"
            format_panel_cinematic(panel_path, temp_framed, target_width=width, target_height=height)
            base_img = Image.open(temp_framed).convert("RGB")
            
            # Subpixel floating-point zoom eliminates integer pixel stepping
            for i in range(total_frames):
                t = i / float(total_frames - 1) if total_frames > 1 else 0.0
                if action == "zoom_out":
                    scale = 1.07 - 0.07 * t
                elif action == "zoom_in":
                    scale = 1.00 + 0.07 * t
                else:
                    scale = 1.00
                    
                box_w = width / scale
                box_h = height / scale
                x0 = (width - box_w) / 2.0
                y0 = (height - box_h) / 2.0
                frame = base_img.resize((width, height), resample=Image.Resampling.BILINEAR, box=(x0, y0, x0 + box_w, y0 + box_h))
                proc.stdin.write(frame.tobytes())
                
            if temp_framed.exists():
                temp_framed.unlink(missing_ok=True)
                
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8")
        proc.wait()
        
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg smooth segment error ({panel_path.name}): {stderr[-300:]}")
            
    except Exception as e:
        if proc.poll() is None:
            proc.kill()
        raise e
        
    return output_segment

def build_synced_story_video(
    scenes: list[dict],
    audio_path: Path,
    srt_path: Path,
    output_path: Path,
    preset_name: str = "shorts",
    watermark_text: str = "Nulls Recap",
    watermark_image: Path = None,
    config: dict = None,
    cache_dir: Path = None,
    end_padding: float = 1.5,
    primary_colour: str = "&H0000E6FF"
) -> Path:
    """
    Builds a frame-perfect, story-synchronized recap video where visual panels
    transition precisely with the spoken narrative.
    
    Generates narration scene-by-scene for 100% perfect audio-visual synchronization,
    preventing any cumulative drift or mismatch.
    
    end_padding adds a breathing buffer at the end of the video (visual hold + clean silence)
    to guarantee the final sentence and visual punchline are never cut off.
    """
    if config is None:
        config = load_config()
        
    width, height = get_resolution(preset_name, config)
    fps = config.get("video", {}).get("fps", 30)
    
    if cache_dir is None:
        cache_dir = output_path.parent / ".scene_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    temp_dir = output_path.parent / f".temp_sync_{output_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    render_tasks = []
    video_segments = []
    audio_segments = []
    all_shifted_cues = []
    total_timeline = 0.0
    
    print(f"[*] Processing {len(scenes)} story scenes for frame-perfect sync...")
    
    try:
        for idx, scene in enumerate(scenes, 1):
            text = scene["text"].strip()
            panels = scene["panels"]
            actions = scene.get("actions", ["zoom_in"] * len(panels))
            
            # Deterministic hash for caching scene audio
            h = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
            scene_audio = cache_dir / f"scene_{h}.mp3"
            scene_srt = cache_dir / f"scene_{h}.srt"
            
            # Generate narration for this specific scene if not cached
            if not scene_audio.exists() or not scene_srt.exists():
                print(f"  [Scene {idx}/{len(scenes)}] Generating audio: \"{text[:45]}...\"")
                tts_engine = config.get("tts", {}).get("engine", "groq")
                if tts_engine == "groq":
                    try:
                        generate_groq_tts(
                            text=text,
                            output_mp3=scene_audio,
                            output_srt=scene_srt,
                            config=config
                        )
                    except Exception as g_ex:
                        print(f"  [!] Groq TTS unavailable ({g_ex}), falling back to Edge-TTS...")
                        generate_edge(
                            text=text,
                            output_mp3=scene_audio,
                            output_srt=scene_srt,
                            config=config
                        )
                elif tts_engine == "elevenlabs":
                    try:
                        generate_elevenlabs(
                            text=text,
                            output_mp3=scene_audio,
                            output_srt=scene_srt,
                            voice_name_or_id="adam",
                            config=config
                        )
                    except Exception as ex:
                        print(f"  [!] ElevenLabs unavailable ({ex}), trying Groq TTS...")
                        try:
                            generate_groq_tts(
                                text=text,
                                output_mp3=scene_audio,
                                output_srt=scene_srt,
                                config=config
                            )
                        except Exception as g_ex:
                            print(f"  [!] Groq TTS unavailable ({g_ex}), falling back to Edge-TTS...")
                            generate_edge(
                                text=text,
                                output_mp3=scene_audio,
                                output_srt=scene_srt,
                                config=config
                            )
                else:
                    generate_edge(
                        text=text,
                        output_mp3=scene_audio,
                        output_srt=scene_srt,
                        config=config
                    )
            else:
                print(f"  [Scene {idx}/{len(scenes)}] Using cached audio ({scene_audio.name})")
                
            scene_dur = get_audio_duration(scene_audio)
            audio_segments.append(scene_audio)
            
            # Shift subtitle cues by the current timeline offset
            shifted = shift_srt_cues(scene_srt, total_timeline)
            all_shifted_cues.extend(shifted)
            
            # Divide scene duration across scene panels
            dur_per_panel = scene_dur / len(panels)
            
            for p_idx, panel in enumerate(panels):
                action = actions[p_idx % len(actions)]
                seg_file = temp_dir / f"seg_{len(video_segments) + 1:04d}.ts"
                
                # If this is the last panel of the final scene, add end_padding for clean breathing room
                is_last_panel = (idx == len(scenes)) and (p_idx == len(panels) - 1)
                panel_duration = dur_per_panel + (end_padding if is_last_panel else 0.0)
                
                render_tasks.append((Path(panel), seg_file, panel_duration, action))
                video_segments.append(seg_file)
                
            total_timeline += scene_dur
            
        print(f"[*] Turbo rendering {len(render_tasks)} panel clips in parallel across Oryon cores...")
        num_workers = min(len(render_tasks), 6)
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    render_scene_clip,
                    panel_path=t[0],
                    output_segment=t[1],
                    duration=t[2],
                    action=t[3],
                    width=width,
                    height=height,
                    fps=fps,
                    threads=2
                )
                for t in render_tasks
            ]
            for f in concurrent.futures.as_completed(futures):
                f.result()
            
        final_timeline = total_timeline + end_padding
        print(f"[+] All scenes rendered. Video duration: {final_timeline:.2f}s (speech: {total_timeline:.2f}s, tail hold: {end_padding:.2f}s)")
        
        # Concat video demuxer
        video_concat_list = temp_dir / "video_concat.txt"
        with open(video_concat_list, "w", encoding="utf-8") as f:
            for vs in video_segments:
                f.write(f"file '{vs.name}'\n")
                
        # Concat audio demuxer
        audio_concat_list = temp_dir / "audio_concat.txt"
        with open(audio_concat_list, "w", encoding="utf-8") as f:
            for asg in audio_segments:
                f.write(f"file '{asg.resolve()}'\n")
                
        # Merge all audio clips into single audio file
        raw_merged_audio = temp_dir / "raw_merged_audio.mp3"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
            "-c", "copy",
            str(raw_merged_audio)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        
        # Pad audio with end_padding silence to match video length perfectly
        merged_audio = temp_dir / "merged_audio.mp3"
        if end_padding > 0:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(raw_merged_audio),
                "-af", f"apad=pad_dur={end_padding:.3f},aresample=44100",
                "-c:a", "libmp3lame",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                str(merged_audio)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        else:
            shutil.copyfile(raw_merged_audio, merged_audio)
            
        # Save master SRT subtitles
        master_srt = srt_path
        master_srt.parent.mkdir(parents=True, exist_ok=True)
        with open(master_srt, "w", encoding="utf-8") as f:
            for c_idx, cue in enumerate(all_shifted_cues, 1):
                clean_cue = normalize_manhwa_glossary(cue)
                f.write(f"{c_idx}\n{clean_cue}\n")
                
        # Also copy merged audio to requested audio_path
        shutil.copyfile(merged_audio, audio_path)
        
        # Subtitle and watermark styling
        fmt_cfg = config.get("video", {}).get("formats", {}).get(preset_name, {})
        font_size = fmt_cfg.get("font_size", 62)
        # MarginV lowered to 360 so subtitles sit lower on screen, keeping character faces clear
        margin_v = fmt_cfg.get("margin_v", 360)
        outline_w = fmt_cfg.get("outline_width", 6)
        
        escaped_srt = str(master_srt.resolve()).replace("\\", "/").replace(":", "\\:")
        fonts_dir = str((BASE_DIR / "assets" / "fonts").resolve()).replace("\\", "/").replace(":", "\\:")
        
        style_str = (
            f"PlayResX={width},PlayResY={height},"
            f"FontName=Anton,FontSize={font_size},"
            f"PrimaryColour={primary_colour},OutlineColour=&H00000000,"
            f"BorderStyle=1,Outline={outline_w},Shadow=0,Alignment=2,MarginV={margin_v}"
        )
        
        sub_filter = f"subtitles='{escaped_srt}':fontsdir='{fonts_dir}':force_style='{style_str}'"
        
        if watermark_image and Path(watermark_image).exists():
            wm_img_path = str(Path(watermark_image).resolve()).replace("\\", "/").replace(":", "\\:")
            wm_cfg = config.get("watermark", {})
            wm_w = wm_cfg.get("badge_width", 320)
            wm_y = wm_cfg.get("badge_y", 1020)
            wm_opacity = wm_cfg.get("opacity", 0.78)
            filter_complex_str = (
                f"movie='{wm_img_path}',scale={wm_w}:-1,format=rgba,colorchannelmixer=aa={wm_opacity}[wm];"
                f"[0:v][wm]overlay=(W-w)/2:{wm_y},{sub_filter}[v_out]"
            )
            filter_args = ["-filter_complex", filter_complex_str, "-map", "[v_out]", "-map", "1:a"]
        else:
            video_filters = [sub_filter]
            if watermark_text:
                escaped_wm = watermark_text.replace("'", "")
                wm_cfg = config.get("watermark", {})
                wm_size = wm_cfg.get("font_size", 28)
                wm_color = wm_cfg.get("font_color", "white@0.50")
                wm_y_ratio = wm_cfg.get("y_ratio", 0.91)
                wm_y = int(height * wm_y_ratio)
                wm_filter = (
                    f"drawtext=text='{escaped_wm}':fontfile='{BASE_DIR}/assets/fonts/SourceSansPro-Bold.ttf':"
                    f"fontsize={wm_size}:fontcolor={wm_color}:shadowcolor=black@0.50:shadowx=2:shadowy=2:x=(w-text_w)/2:y={wm_y}"
                )
                video_filters.append(wm_filter)
            filter_args = ["-map", "0:v", "-map", "1:a", "-vf", ",".join(video_filters)]
            
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(video_concat_list),
            "-i", str(merged_audio)
        ] + filter_args + [
            "-t", f"{final_timeline:.3f}",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-threads", "8",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
        
        res = subprocess.run(final_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg final assembly error: {res.stderr[-400:]}")
            
        print(f"[+] Story recap video rendered successfully: {output_path.name} ({final_timeline:.1f}s)")
        return output_path
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

