from pathlib import Path

def get_motion_filter(motion_type: str, duration: float, width: int = 1080, height: int = 1920, fps: int = 30) -> str:
    """
    Generates buttery smooth, continuous Ken Burns motion filters for FFmpeg.
    Uses monotonic time parameter (on/total_frames) to eliminate all jitter and clamp steps.
    """
    total_frames = max(1, int(round(duration * fps)))
    
    if motion_type == "zoom_in":
        # Smooth cinematic zoom-in towards center (1.00 -> 1.08)
        return (
            f"zoompan=z='1.0+0.08*(on/{total_frames})':d={total_frames}:"
            f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':s={width}x{height}:fps={fps}"
        )
    elif motion_type == "zoom_out":
        # Smooth cinematic zoom-out (1.08 -> 1.00)
        return (
            f"zoompan=z='1.08-0.08*(on/{total_frames})':d={total_frames}:"
            f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':s={width}x{height}:fps={fps}"
        )
    elif motion_type == "pan_down":
        # Slow, graceful vertical scroll downward (ideal for full body reveals)
        return (
            f"zoompan=z='1.05':d={total_frames}:"
            f"x='(iw-iw/zoom)/2':y='(on/{total_frames})*(ih-ih/zoom)':s={width}x{height}:fps={fps}"
        )
    elif motion_type == "pan_up":
        # Slow vertical scroll upward (from weapon/feet to face)
        return (
            f"zoompan=z='1.05':d={total_frames}:"
            f"x='(iw-iw/zoom)/2':y='(1-on/{total_frames})*(ih-ih/zoom)':s={width}x{height}:fps={fps}"
        )
    else:
        # Static hold
        return f"scale={width}:{height},fps={fps}"
