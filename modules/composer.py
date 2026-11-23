import os
import shutil
import subprocess
from pathlib import Path
from modules.preset import load_config, get_resolution
from modules.motion import get_motion_filter
from modules.narrator import get_audio_duration

BASE_DIR = Path(__file__).resolve().parent.parent

def build_recap_video(
    frame_paths: list[Path],
    audio_path: Path,
    srt_path: Path | None,
    output_path: Path,
    bgm_path: Path | None = None,
    preset_name: str = "shorts",
    watermark_text: str | None = None,
    motion_enabled: bool = True,
    burn_subs: bool = True,
    config: dict = None
) -> Path:
    """
    Assembles panel frames, narration audio, optional BGM, watermark, and styled subtitles into a final video.
    """
    if config is None:
        config = load_config()
        
    width, height = get_resolution(preset_name, config)
    fps = config.get("video", {}).get("fps", 30)
    audio_dur = get_audio_duration(audio_path)
    
    if audio_dur <= 0.0:
        raise ValueError(f"Invalid or empty audio track: {audio_path}")
        
    if not frame_paths:
        raise ValueError("No frames provided for video rendering")
        
    num_frames = len(frame_paths)
    time_per_frame = audio_dur / num_frames
    print(f"[*] Total audio duration: {audio_dur:.2f}s | Panels: {num_frames} | Avg panel duration: {time_per_frame:.2f}s")
    
    # Working temp directory for clips
    temp_dir = output_path.parent / ".temp_render"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    motion_modes = ["zoom_in", "zoom_out", "pan_down", "zoom_in", "zoom_out"]
    segment_files = []
    
    try:
        if motion_enabled:
            print("[*] Rendering Ken Burns motion for panels...")
            for i, fp in enumerate(frame_paths):
                mode = motion_modes[i % len(motion_modes)]
                seg_file = temp_dir / f"seg_{i:04d}.ts"
                vf = get_motion_filter(mode, time_per_frame, width, height, fps)
                
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(fp),
                    "-vf", vf,
                    "-t", f"{time_per_frame:.3f}",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    "-f", "mpegts",
                    str(seg_file)
                ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    raise RuntimeError(f"Error rendering segment {i}: {res.stderr[-300:]}")
                segment_files.append(seg_file)
                
            # Concat demuxer list
            concat_list = temp_dir / "concat.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for seg in segment_files:
                    f.write(f"file '{seg.name}'\n")
                    
            video_input_args = ["-f", "concat", "-safe", "0", "-i", str(concat_list)]
        else:
            concat_list = temp_dir / "concat_static.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for fp in frame_paths:
                    f.write(f"file '{fp.resolve()}'\n")
                    f.write(f"duration {time_per_frame:.3f}\n")
                f.write(f"file '{frame_paths[-1].resolve()}'\n")
                
            video_input_args = ["-f", "concat", "-safe", "0", "-i", str(concat_list)]

        # Audio mixing
        audio_cfg = config.get("audio", {})
        voice_vol = audio_cfg.get("voice_volume", 1.0)
        bgm_vol = audio_cfg.get("bgm_volume", 0.15)
        
        inputs = video_input_args + ["-i", str(audio_path)]
        
        if bgm_path and Path(bgm_path).exists():
            print(f"[*] Incorporating background music: {Path(bgm_path).name} (vol={bgm_vol})")
            inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
            fade_out_start = max(0.0, audio_dur - 2.0)
            filter_complex = (
                f"[1:a]volume={voice_vol}[voice];"
                f"[2:a]volume={bgm_vol},afade=t=out:st={fade_out_start:.2f}:d=2[bgm];"
                f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            audio_map_args = ["-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]"]
        else:
            audio_map_args = ["-map", "0:v", "-map", "1:a"]

        # Video filters
        video_filters = []
        if not motion_enabled:
            video_filters.append(f"scale={width}:{height}")
            
        # Watermark
        wm_cfg = config.get("watermark", {})
        if watermark_text is None and wm_cfg.get("enabled", True):
            watermark_text = wm_cfg.get("text", "Nulls Recap")
            
        if watermark_text:
            escaped_wm = watermark_text.replace("'", "")
            wm_font = wm_cfg.get("font_file", f"{BASE_DIR}/assets/fonts/SourceSansPro-Bold.ttf")
            wm_size = wm_cfg.get("font_size", 28)
            wm_col = wm_cfg.get("font_color", "white@0.45")
            wm_y = int(height * 0.82) if preset_name in ("shorts", "tiktok") else int(height * 0.90)
            wm_filter = (
                f"drawtext=text='{escaped_wm}':fontfile='{wm_font}':"
                f"fontsize={wm_size}:fontcolor={wm_col}:shadowcolor=black@0.35:shadowx=2:shadowy=2:x=(w-text_w)/2:y={wm_y}"
            )
            video_filters.append(wm_filter)

        # Subtitles
        if burn_subs and srt_path and Path(srt_path).exists():
            sub_cfg = config.get("subtitles", {})
            fmt_cfg = config.get("video", {}).get("formats", {}).get(preset_name, {})
            
            font_size = fmt_cfg.get("font_size", sub_cfg.get("font_size", 24))
            margin_v = fmt_cfg.get("margin_v", sub_cfg.get("margin_v", 650))
            outline_w = fmt_cfg.get("outline_width", sub_cfg.get("outline_width", 4))
            font_name = sub_cfg.get("font_name", "Anton")
            primary_col = sub_cfg.get("primary_color", "&H0000E6FF") # Bright viral yellow
            outline_col = sub_cfg.get("outline_color", "&H00000000") # Black
            alignment = sub_cfg.get("alignment", 2)
            
            escaped_srt = str(Path(srt_path).resolve()).replace("\\", "/").replace(":", "\\:")
            fonts_dir = str((BASE_DIR / "assets" / "fonts").resolve()).replace("\\", "/").replace(":", "\\:")
            
            style_str = (
                f"PlayResX={width},PlayResY={height},"
                f"FontName={font_name},FontSize={font_size},"
                f"PrimaryColour={primary_col},OutlineColour={outline_col},"
                f"BorderStyle=1,Outline={outline_w},Shadow=0,Alignment={alignment},MarginV={margin_v}"
            )
            video_filters.append(f"subtitles='{escaped_srt}':fontsdir='{fonts_dir}':force_style='{style_str}'")

        vf_args = []
        if video_filters:
            vf_args = ["-vf", ",".join(video_filters)]

        # Final assembly command
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_cmd = (
            ["ffmpeg", "-y"]
            + inputs
            + audio_map_args
            + vf_args
            + [
                "-t", f"{audio_dur:.3f}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path)
            ]
        )

        print(f"[*] Encoding final {preset_name.upper()} video ({width}x{height})...")
        res = subprocess.run(final_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg render error: {res.stderr[-400:]}")
            
        print(f"[+] Final recap video rendered successfully: {output_path} ({audio_dur:.1f}s)")
        return output_path
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
