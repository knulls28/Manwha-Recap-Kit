import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def load_env_file():
    """Zero-dependency loader for .env files."""
    for p in [BASE_DIR / ".env", Path.cwd() / ".env"]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key and key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass
            break

load_env_file()

def load_config():
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        fallback = BASE_DIR / "config.example.json"
        if fallback.exists():
            config_path = fallback
        else:
            raise FileNotFoundError(f"Config file not found at {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_voice_id(voice_name_or_id: str, config: dict = None) -> str:
    if config is None:
        config = load_config()
    voices = config.get("tts", {}).get("elevenlabs", {}).get("voices", {})
    lower_key = voice_name_or_id.lower()
    return voices.get(lower_key, voice_name_or_id)

def get_resolution(preset_name: str, config: dict = None) -> tuple[int, int]:
    if config is None:
        config = load_config()
    formats = config.get("video", {}).get("formats", {})
    fmt = formats.get(preset_name.lower(), formats.get("youtube", {"width": 1920, "height": 1080}))
    return fmt["width"], fmt["height"]
