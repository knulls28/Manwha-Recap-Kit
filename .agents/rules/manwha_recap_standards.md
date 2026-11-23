# Manhwa Recap Video Standards & Guidelines

This rule defines the operational standards, visual invariants, audio sync rules, and layout constraints for generating manhwa and webtoon recap videos in this workspace.

---

## 1. Panel Filtering & Exclusion Invariants

- **Exclude Title & Volume Cards:**
  - Strip out all title cover pages, manhwa metadata cards, and chapter start headers (e.g., `ch01_0001.png`, `ch02_0001.png` showing "VOL. 2").
  - Strip out any volume numbers, release banners, or manhwa logo splashes.
- **Exclude Scanlator & Promo Banners:**
  - Exclude all scanlation team recruitment pages, Discord promo cards, donation links, and credit end-cards.
- **Clean Slicing:**
  - Ensure panel segmentation trims horizontal whitespace gutters cleanly so panels do not overlap or cut through speech bubbles.

---

## 2. Layout Geometry & Safe Zones (1080x1920 Vertical 9:16)

- **Art Showcase Zone (Top 75%):**
  - Keep $y = 0$ to $y \approx 1440$ completely free from subtitles and overlays to showcase character faces and action linework.
- **Subtitle Styling & Placement:**
  - **Single-Line Only Invariant:** Cues must be grouped to at most 1–3 words (max 24 characters). Captions must **NEVER** wrap into multiple stacked lines.
  - **Font:** Anton (or clean impactful sans-serif bold fallback).
  - **Font Size:** 62pt.
  - **Primary Color:** Bold vibrant yellow (`&H0000E6FF`).
  - **Outline:** 6px solid black outline (`&H00000000`).
  - **Alignment:** Bottom center (`Alignment=2`).
  - **Vertical Margin (`MarginV`):** `360` (places subtitle text comfortably between $y \approx 1500$ and $y \approx 1620$).
- **Branded Watermark:**
  - **Text:** `Nulls Recap` (exact casing).
  - **Styling:** 32pt semi-transparent white (`white@0.5` or `&H80FFFFFF`) with subtle shadow.
  - **Position:** Horizontal center, fixed at $y = \text{int}(\text{height} \times 0.91)$ (approx. $y = 1747$).
  - **Zero Overlap:** The watermark must sit strictly below the subtitles and never collide with captions.

---

## 3. Audio-Visual Synchronization & Narration Flow

- **Strict 1:1 Character & Scene Pairing:**
  - Never lump multiple character introductions into a single bulk sentence with arbitrary $T/N$ time division.
  - Every named entity or plot beat must map directly to its specific panel (e.g., Hercules $\rightarrow$ Hercules panel, Wukong $\rightarrow$ Wukong panel, Yuwon $\rightarrow$ Yuwon panel).
- **Ending Tail Buffer (Cutoff Prevention):**
  - Always append `1.2s` to `1.5s` of visual hold (`end_padding=1.5`) on the final scene.
  - Pad the final audio stream with matching silence (`-af apad=pad_dur=1.5`).
  - Always include the final dramatic punchline/climax beat (e.g., *"Now, let's start."*) so videos resolve cleanly.
- **Continuous VO & No Static Outro Cards:**
  - Do **NOT** insert static graphic outro cards, subscribe splash screens, or transition breaks between chapters.
  - For multi-chapter full recaps, maintain continuous voiceover that bridges directly from the climax of one chapter into the opening beat of the next.

---

## 4. Jitter-Free Motion Engine Standards

- **Forbidden Filters:**
  - Never use FFmpeg's `zoompan` or integer `crop` filters for Ken Burns motion or vertical panning. Integer truncation causes 1-pixel trembling/shaking on manhwa linework.
- **Mandatory Subpixel Resampling:**
  - Use Pillow floating-point subpixel box resampling (`box=(x0, y0, x1, y1)` with bilinear/lanczos interpolation) piped directly to FFmpeg stdin as `rawvideo rgb24`.

---

## 5. Workspace Directory Structure

```
<Project Root>/
├── Chapters/          # Dedicated directory for raw CBZ/ZIP archives
├── panels/            # Clean sliced individual panels
├── audio/             # Rendered voiceover MP3s and timed SRTs
├── .scene_cache/      # Per-scene TTS hash cache (preserves quota)
└── output/            # Exported recap videos
    ├── Chapter 01/
    ├── Chapter 02/
    └── Seamless Full/
```

---

## 6. Character Name Accuracy & Glossary Invariants

- **Official Romanization & Consistency:**
  - Always note down and use the exact, official manhwa romanization for character names in both script text and subtitles (e.g., **Kim Yuwon**, **Chronos**, **Son Wukong**, **Hercules**).
  - Never allow TTS engines or speech-to-text models to guess or slur Korean names (e.g. "Yuwon" pronounced as "Yuan" or "You-on"). Use **Kim Yuwon** in scripts to ensure authentic Korean pronunciation.
- **Automated Subtitle Glossary Filter:**
  - Subtitle cues must pass through `normalize_manhwa_glossary()` to replace any ASR phonetic approximations (`YUAN`, `YUON`, `YUWAN`, `YOO-WON` $\rightarrow$ `KIM YUWON` / `YUWON`).
- **Lore Context Integration:**
  - Incorporate relevant factions, locations, and groups (e.g. *Cheong-Sol University* students, *High Rankers*, *Outer Gods*) to keep narration immersive and true to the source material.

