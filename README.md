# 🎬 Webtoon & Comic Recap Video Creation Engine

An automated, high-retention video creation pipeline and **AI Agent Skill** designed to produce frame-perfect, jitter-free recap videos (YouTube Shorts, TikTok, Instagram Reels, and 16:9 widescreen) from digital comic and webtoon chapters (CBZ, ZIP, or image folders).

---

## ⚡ Key Highlights

- **🤖 2-Question Agent Protocol**: When invoked as an AI Agent Skill, the agent only asks two questions:
  1. Path to input chapters (`chapters_dir`)
  2. Path to output project workspace (`project_dir`)
  From there, the agent autonomously executes extraction, slicing, scriptwriting, voiceover, and parallel rendering.
- **🎥 Jitter-Free Subpixel Motion**: Replaces native FFmpeg integer-stepping zoompan with floating-point subpixel box resampling via Pillow, eliminating 1-pixel vibration on fine linework.
- **🗣️ High-Retention Voiceover**: Built-in free Edge-TTS support with scene-level MD5 caching to ensure zero wasted compute on re-renders.
- **🎨 Dynamic Libass Subtitles**: Single-line 3-word punchy captions with neon fills and thick contrast borders positioned in the lower third.
- **🛡️ Anti-Theft Watermark Badge**: Translucent custom crest/sticker badge overlay positioned directly above subtitles to prevent unauthorized scraping while keeping character art clear.
- **🚀 Multi-Core Parallel Rendering**: Turbo renders panel clips concurrently across all available CPU cores.

---

## 📁 Repository Structure

```
├── .agents/skills/manwha-recap/
│   └── SKILL.md              # Antigravity / Agent Skill definition
├── modules/
│   ├── slicer.py             # Variance-based gutter cut detection
│   ├── formatter.py          # Cinematic background blur and padding
│   ├── story_sync.py         # Parallel rendering & subpixel motion engine
│   ├── narrator.py           # Narration synthesis & subtitle generator
│   └── preset.py             # Config & resolution preset loader
├── assets/
│   ├── fonts/                # Bold display fonts (Anton, SourceSansPro, etc.)
│   └── nulls_crest_transparent.png  # Default channel badge overlay
├── create_recap.py           # Interactive CLI tool for manual execution
├── config.example.json       # Clean template configuration
└── requirements.txt          # Python dependencies
```

---

## 🛠️ Installation & Prerequisites

### 1. System Requirements
- **Python**: 3.10 or higher
- **FFmpeg**: Must be installed with `libx264` and `libass` support:
  ```bash
  # Debian / Ubuntu / Termux
  pkg install ffmpeg python
  # or
  sudo apt install ffmpeg python3 python3-pip
  ```

### 2. Python Packages
```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

### Option A: Using with an AI Agent (Antigravity Skill)
Simply install or reference the skill from `.agents/skills/manwha-recap/SKILL.md`.
When you ask the agent:
> *"Create a video recap for Chapter 1"*

The agent will prompt you for:
1. The location of your raw chapter archives.
2. The destination project directory.

Once provided, the agent runs the entire 11-step pipeline autonomously and delivers the finished MP4 with clickable links.

### Option B: Using the Interactive CLI Tool
Run the script directly in your terminal:
```bash
python create_recap.py
```
Or pass arguments directly:
```bash
python create_recap.py \
  --chapters-dir "/path/to/chapters" \
  --project-dir "./Projects/MySeries" \
  --chapter 1 \
  --series-title "My Comic Series"
```

---

## ⚙️ Configuration

Copy `config.example.json` to `config.json` to customize default voices, fonts, and dimensions:

```json
{
  "tts": {
    "engine": "edge",
    "edge": {
      "default_voice": "en-US-BrianNeural",
      "rate": "+15%"
    }
  },
  "watermark": {
    "enabled": true,
    "badge_width": 320,
    "badge_y": 1020,
    "opacity": 0.78
  },
  "video": {
    "default_preset": "shorts"
  }
}
```

---

## 📄 License

MIT License. Free to use, modify, and distribute.
