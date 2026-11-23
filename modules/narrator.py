import os
import re
import json
import base64
import asyncio
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from modules.preset import load_config, get_voice_id

def format_timestamp(seconds: float) -> str:
    """Converts seconds into SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def get_audio_duration(file_path: Path | str) -> float:
    """Returns exact duration in seconds using ffprobe"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(res.stdout.strip())
    except (ValueError, TypeError):
        return 0.0

def normalize_manhwa_glossary(text: str) -> str:
    """
    Normalizes phonetic and ASR misrecognitions of character names, locations,
    and terms in webtoon recap scripts to ensure 100% correct subtitle typography.
    """
    glossary = [
        # Protagonist (Kim Yuwon)
        (r'\bKIM\s+(?:YUAN|YUON|YUWAN|YOO-?W[OA]N|YOU-?W[OA]N|YU-?W[OA]N|YU-?H[OA]N|YOO-?H[OA]N)\b', 'KIM YUWON'),
        (r'\b(?:YUAN|YUON|YUWAN|YOO-?W[OA]N|YOU-?W[OA]N|YU-?W[OA]N|YU-?H[OA]N|YOO-?H[OA]N)(\'S)?\b', r'YUWON\1'),
        (r'\bYOU\s+W[OA]N\b', 'YUWON'),
        # Gods & Entities
        (r'\bCHRONOS\b', 'CHRONOS'),
        (r'\bHERCULES\b', 'HERCULES'),
        (r'\bSON\s+WUKONG\b', 'SON WUKONG'),
        (r'\bWUKONG\b', 'WUKONG'),
        (r'\bASURA\b', 'ASURA'),
        (r'\bSURTR\b', 'SURTR'),
        (r'\bODIN\b', 'ODIN'),
        (r'\bHARGAAN\b', 'HARGAAN'),
        # Locations & Terms
        (r'\b(?:CHEONG-?SOL|CHANGSUL)\b', 'CHEONG-SOL'),
    ]
    for pattern, replacement in glossary:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def alignment_to_srt(
    alignment: dict,
    time_offset: float = 0.0,
    words_per_line: int = 3,
    uppercase: bool = True
) -> tuple[list[str], float]:
    """
    Parses ElevenLabs character-level alignment data into grouped, punchy SRT subtitle cues.
    Matches the fast-paced style of viral YouTube Shorts (2-4 words per cue, uppercase).
    """
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    
    if not chars:
        return [], time_offset
        
    words = []
    current_word = []
    word_start = None
    word_end = None
    
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if current_word:
                words.append({
                    "word": "".join(current_word),
                    "start": word_start + time_offset,
                    "end": word_end + time_offset
                })
                current_word = []
                word_start = None
                word_end = None
        else:
            if word_start is None:
                word_start = s
            word_end = e
            current_word.append(c)
            
    if current_word:
        words.append({
            "word": "".join(current_word),
            "start": word_start + time_offset,
            "end": word_end + time_offset
        })
        
    # Group words into short punchy subtitle lines (default 3 words)
    sub_entries = []
    i = 0
    while i < len(words):
        chunk = words[i:i + words_per_line]
        line_text = " ".join(w["word"] for w in chunk)
        if uppercase:
            line_text = line_text.upper()
            
        t_start = chunk[0]["start"]
        t_end = chunk[-1]["end"]
        
        # Smooth duration buffer
        t_end = max(t_end, t_start + 0.5)
        
        sub_entries.append((
            f"{format_timestamp(t_start)} --> {format_timestamp(t_end)}\n"
            f"{line_text}\n"
        ))
        i += words_per_line
        
    max_end = ends[-1] + time_offset if ends else time_offset
    return sub_entries, max_end

def generate_elevenlabs(
    text: str,
    output_mp3: Path,
    output_srt: Path,
    voice_name_or_id: str = "adam",
    config: dict = None
) -> float:
    """
    Generates narration audio and exact synchronized SRT subtitles using ElevenLabs.
    """
    if config is None:
        config = load_config()
        
    el_cfg = config.get("tts", {}).get("elevenlabs", {})
    api_key = os.environ.get("ELEVENLABS_API_KEY") or el_cfg.get("api_key")
    if not api_key or api_key.startswith("PASTE_"):
        raise ValueError("Missing ElevenLabs API key in config.json")
        
    sub_cfg = config.get("subtitles", {})
    words_per_line = sub_cfg.get("words_per_cue", 3)
    uppercase = sub_cfg.get("uppercase", True)
    
    voice_id = get_voice_id(voice_name_or_id, config)
    model_id = el_cfg.get("model_id", "eleven_multilingual_v2")
    stability = el_cfg.get("stability", 0.5)
    similarity = el_cfg.get("similarity_boost", 0.75)
    
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
        
    chunks = []
    curr = []
    curr_len = 0
    for p in paragraphs:
        if curr_len + len(p) > 3000:
            chunks.append("\n".join(curr))
            curr = [p]
            curr_len = len(p)
        else:
            curr.append(p)
            curr_len += len(p)
    if curr:
        chunks.append("\n".join(curr))
        
    output_mp3.parent.mkdir(parents=True, exist_ok=True)
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    
    combined_audio = bytearray()
    all_srt_entries = []
    time_offset = 0.0
    
    print(f"[*] Generating ElevenLabs narration with voice: {voice_name_or_id} ({voice_id})...")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    
    for i, chunk in enumerate(chunks):
        payload = json.dumps({
            "text": chunk,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity
            }
        }).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json"
            }
        )
        
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                audio_bytes = base64.b64decode(data.get("audio_base64", ""))
                combined_audio.extend(audio_bytes)
                
                align = data.get("alignment", {})
                entries, new_offset = alignment_to_srt(
                    align,
                    time_offset=time_offset,
                    words_per_line=words_per_line,
                    uppercase=uppercase
                )
                all_srt_entries.extend(entries)
                time_offset = new_offset + 0.25
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"ElevenLabs API Error {e.code}: {err_body}")
            
    # Write MP3 audio
    with open(output_mp3, "wb") as f:
        f.write(combined_audio)
        
    # Write SRT subtitles
    with open(output_srt, "w", encoding="utf-8") as f:
        for idx, entry in enumerate(all_srt_entries, 1):
            f.write(f"{idx}\n{entry}\n")
            
    duration = get_audio_duration(output_mp3)
    print(f"[+] Audio generated: {output_mp3.name} ({duration:.1f}s)")
    print(f"[+] Subtitles generated: {output_srt.name} ({len(all_srt_entries)} cues)")
    return duration

async def _run_edge_tts(text: str, output_mp3: Path, output_srt: Path, voice: str, rate: str, uppercase: bool = True):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    submaker = edge_tts.SubMaker()
    with open(output_mp3, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
                
    srt_content = submaker.get_srt()
    if uppercase:
        lines = []
        for line in srt_content.splitlines():
            # Keep index and timestamps unchanged
            if "-->" not in line and not line.strip().isdigit():
                lines.append(line.upper())
            else:
                lines.append(line)
        srt_content = "\n".join(lines)
        
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(srt_content)

def generate_edge(
    text: str,
    output_mp3: Path,
    output_srt: Path,
    voice: str = None,
    rate: str = None,
    config: dict = None
) -> float:
    """Generates punchy, energetic narration using Edge-TTS with Groq Whisper 1-line subtitles"""
    if config is None:
        config = load_config()
    edge_cfg = config.get("tts", {}).get("edge", {})
    voice = voice or edge_cfg.get("default_voice", "en-US-GuyNeural")
    rate = rate or edge_cfg.get("rate", "+15%")
    uppercase = config.get("subtitles", {}).get("uppercase", True)
    
    output_mp3.parent.mkdir(parents=True, exist_ok=True)
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Generating Edge-TTS narration with voice: {voice} (rate: {rate})...")
    asyncio.run(_run_edge_tts(text, output_mp3, output_srt, voice, rate, uppercase=uppercase))
    
    # Use Groq Whisper for punchy, synchronized single-line SRT subtitles
    groq_key = os.environ.get("GROQ_API_KEY") or config.get("tts", {}).get("groq", {}).get("api_key")
    if groq_key and not groq_key.startswith("PASTE_"):
        try:
            whisper_model = config.get("tts", {}).get("groq", {}).get("whisper_model", "whisper-large-v3-turbo")
            transcribe_cmd = [
                "curl", "-s", "-X", "POST", "https://api.groq.com/openai/v1/audio/transcriptions",
                "-H", f"Authorization: Bearer {groq_key}",
                "-F", f"file=@{output_mp3}",
                "-F", f"model={whisper_model}",
                "-F", "response_format=verbose_json",
                "-F", "timestamp_granularities[]=word"
            ]
            res = subprocess.run(transcribe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                words = data.get("words", [])
                if words:
                    max_words = config.get("subtitles", {}).get("words_per_cue", 3)
                    max_chars = 24
                    all_cues = []
                    curr_words = []
                    c_start = None
                    c_end = None
                    for w_obj in words:
                        w = w_obj["word"].strip()
                        if not w:
                            continue
                        w_start = w_obj["start"]
                        w_end = w_obj["end"]
                        if not curr_words:
                            curr_words = [w]
                            c_start = w_start
                            c_end = w_end
                        else:
                            tentative = " ".join(curr_words + [w])
                            if len(curr_words) >= max_words or len(tentative) > max_chars:
                                line = normalize_manhwa_glossary(" ".join(curr_words))
                                if uppercase:
                                    line = line.upper()
                                all_cues.append(f"{len(all_cues) + 1}\n{format_timestamp(c_start)} --> {format_timestamp(c_end)}\n{line}\n")
                                curr_words = [w]
                                c_start = w_start
                                c_end = w_end
                            else:
                                curr_words.append(w)
                                c_end = w_end
                    if curr_words:
                        line = normalize_manhwa_glossary(" ".join(curr_words))
                        if uppercase:
                            line = line.upper()
                        all_cues.append(f"{len(all_cues) + 1}\n{format_timestamp(c_start)} --> {format_timestamp(c_end)}\n{line}\n")
                    with open(output_srt, "w", encoding="utf-8") as f:
                        f.write("\n".join(all_cues))
        except Exception as e:
            print(f"  [!] Whisper 1-line alignment skipped ({e}), using edge submaker")
            
    duration = get_audio_duration(output_mp3)
    print(f"[+] Audio generated: {output_mp3.name} ({duration:.1f}s)")
    return duration

def generate_groq_tts(
    text: str,
    output_mp3: Path,
    output_srt: Path,
    voice: str = None,
    config: dict = None
) -> float:
    """
    Generates narration audio using Groq's speech API and transcribes word/segment cues
    using Groq's ultra-fast Whisper endpoint for synchronized subtitles.
    """
    if config is None:
        config = load_config()
        
    groq_cfg = config.get("tts", {}).get("groq", {})
    api_key = groq_cfg.get("api_key")
    if not api_key:
        raise ValueError("Missing Groq API key in config.json")
        
    tts_model = groq_cfg.get("tts_model", "canopylabs/orpheus-v1-english")
    whisper_model = groq_cfg.get("whisper_model", "whisper-large-v3-turbo")
    voice = voice or groq_cfg.get("default_voice", "daniel")
    
    output_mp3.parent.mkdir(parents=True, exist_ok=True)
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[*] Generating Groq TTS speech with model: {tts_model} (voice: {voice})...")
    speech_url = "https://api.groq.com/openai/v1/audio/speech"
    payload = json.dumps({
        "model": tts_model,
        "input": text,
        "voice": voice,
        "response_format": "wav"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        speech_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity-Recap/1.0"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Groq Speech Error {e.code}: {err_body}")
        
    temp_wav = output_mp3.parent / f"temp_{output_mp3.stem}.wav"
    with open(temp_wav, "wb") as f:
        f.write(audio_bytes)
        
    # Convert WAV to high quality MP3
    subprocess.run([
        "ffmpeg", "-y", "-i", str(temp_wav),
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(output_mp3)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    temp_wav.unlink(missing_ok=True)
        
    # Transcribe with Groq Whisper for synchronized single-line SRT subtitles
    print(f"[*] Transcribing Groq audio with Whisper ({whisper_model})...")
    transcribe_cmd = [
        "curl", "-s", "-X", "POST", "https://api.groq.com/openai/v1/audio/transcriptions",
        "-H", f"Authorization: Bearer {api_key}",
        "-F", f"file=@{output_mp3}",
        "-F", f"model={whisper_model}",
        "-F", "response_format=verbose_json",
        "-F", "timestamp_granularities[]=word"
    ]
    res = subprocess.run(transcribe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and res.stdout.strip():
        data = json.loads(res.stdout)
        words = data.get("words", [])
        uppercase = config.get("subtitles", {}).get("uppercase", True)
        
        all_cues = []
        if words:
            # Group into short, punchy 1-line cues (max 3 words, max 26 chars)
            max_words = config.get("subtitles", {}).get("words_per_cue", 3)
            max_chars = 26
            
            curr_words = []
            c_start = None
            c_end = None
            
            for w_obj in words:
                w = w_obj["word"].strip()
                if not w:
                    continue
                w_start = w_obj["start"]
                w_end = w_obj["end"]
                
                if not curr_words:
                    curr_words = [w]
                    c_start = w_start
                    c_end = w_end
                else:
                    tentative = " ".join(curr_words + [w])
                    if len(curr_words) >= max_words or len(tentative) > max_chars:
                        line = normalize_manhwa_glossary(" ".join(curr_words))
                        if uppercase:
                            line = line.upper()
                        all_cues.append(f"{len(all_cues) + 1}\n{format_timestamp(c_start)} --> {format_timestamp(c_end)}\n{line}\n")
                        curr_words = [w]
                        c_start = w_start
                        c_end = w_end
                    else:
                        curr_words.append(w)
                        c_end = w_end
                        
            if curr_words:
                line = normalize_manhwa_glossary(" ".join(curr_words))
                if uppercase:
                    line = line.upper()
                all_cues.append(f"{len(all_cues) + 1}\n{format_timestamp(c_start)} --> {format_timestamp(c_end)}\n{line}\n")
        else:
            segments = data.get("segments", [])
            for s_idx, seg in enumerate(segments, 1):
                s_start = format_timestamp(seg.get("start", 0.0))
                s_end = format_timestamp(max(seg.get("end", 0.0), seg.get("start", 0.0) + 0.5))
                seg_text = normalize_manhwa_glossary(seg.get("text", "").strip())
                if uppercase:
                    seg_text = seg_text.upper()
                all_cues.append(f"{s_idx}\n{s_start} --> {s_end}\n{seg_text}\n")
                
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write("\n".join(all_cues))
            
    duration = get_audio_duration(output_mp3)
    print(f"[+] Groq Audio generated: {output_mp3.name} ({duration:.1f}s)")
    return duration

def generate_narration(
    text: str,
    output_mp3: Path,
    output_srt: Path,
    engine: str = None,
    voice: str = None,
    config: dict = None
) -> float:
    """Master narration generator selecting between ElevenLabs, Groq, and Edge-TTS"""
    if config is None:
        config = load_config()
    tts_cfg = config.get("tts", {})
    if engine is None:
        engine = tts_cfg.get("engine", "elevenlabs")
        
    if engine == "elevenlabs":
        voice = voice or tts_cfg.get("elevenlabs", {}).get("default_voice", "adam")
        return generate_elevenlabs(text, output_mp3, output_srt, voice_name_or_id=voice, config=config)
    elif engine == "groq":
        return generate_groq_tts(text, output_mp3, output_srt, voice=voice, config=config)
    else:
        voice = voice or tts_cfg.get("edge", {}).get("default_voice", "en-US-ChristopherNeural")
        rate = tts_cfg.get("edge", {}).get("rate", "+10%")
        return generate_edge(text, output_mp3, output_srt, voice=voice, rate=rate, config=config)
