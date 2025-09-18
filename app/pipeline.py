import subprocess
from pathlib import Path
from typing import Optional, List, Dict
import re
from collections import Counter
import json

from faster_whisper import WhisperModel
import pyttsx3
from googletrans import Translator
from gtts import gTTS


# ----------------- EXTRACCIÓN DE AUDIO -----------------

def extract_audio(video_path: Path) -> Path:
    """Extrae el audio del video con FFmpeg y devuelve la ruta del .wav."""
    audio_path = video_path.with_suffix(".wav")

    cmd = [
        "ffmpeg",
        "-y",                 # sobrescribir si existe
        "-i", str(video_path),
        "-vn",                # sin video
        "-acodec", "pcm_s16le",
        "-ar", "16000",       # 16 kHz
        "-ac", "1",           # 1 canal (mono)
        str(audio_path),
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError("No se encontró 'ffmpeg' en el PATH. Instalalo y probá de nuevo.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg error: {e.stderr.decode()}")

    return audio_path


# ----------------- TRANSCRIPCIÓN -----------------

def transcribe(audio_path: Path, language: Optional[str] = None) -> List[Dict]:
    """
    Transcribe con faster-whisper -> lista de {start, end, text}.
    """
    model = WhisperModel("small", compute_type="int8")  # CPU-friendly
    segments, _info = model.transcribe(
        str(audio_path),
        language=language,  # None => autodetección
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
    )

    results: List[Dict] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            results.append({"start": float(seg.start), "end": float(seg.end), "text": text})
    return results


# ----------------- ARCHIVOS DE SUBTÍTULOS -----------------

def write_srt(segments: List[Dict], srt_path: Path) -> None:
    """Crea archivo .srt a partir de los segmentos."""
    def ts(seconds: float) -> str:
        ms = int((seconds - int(seconds)) * 1000)
        sec = int(seconds) % 60
        minutes = (int(seconds) // 60) % 60
        hours = int(seconds) // 3600
        return f"{hours:02d}:{minutes:02d}:{sec:02d},{ms:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n{ts(seg['start'])} --> {ts(seg['end'])}\n{seg['text']}\n\n")


def write_vtt(segments: List[Dict], vtt_path: Path) -> None:
    """Crea archivo .vtt (WebVTT) a partir de los segmentos."""
    def ts(seconds: float) -> str:
        ms = int((seconds - int(seconds)) * 1000)
        sec = int(seconds) % 60
        minutes = (int(seconds) // 60) % 60
        hours = int(seconds) // 3600
        return f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"

    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            f.write(f"{ts(seg['start'])} --> {ts(seg['end'])}\n{seg['text']}\n\n")


# ----------------- RESUMEN -----------------

def summarize(full_text: str, max_sentences: int = 4) -> str:
    """Resumen por frecuencia de palabras (simple, offline)."""
    text = re.sub(r"\s+", " ", full_text).strip()
    if not text:
        return "No se pudo generar un resumen."

    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= max_sentences:
        return text

    words = re.findall(r"[a-záéíóúñüA-ZÁÉÍÓÚÑÜ]+", text.lower())
    stop = set("""
        de la que el en y a los las un una para con por del se al lo es
        como más muy ya no sí o pero también si esto esta este estos estas
        fue fueron son ser sobre entre hasta donde cuando porque
    """.split())
    words = [w for w in words if w not in stop and len(w) > 2]
    freq = Counter(words)

    scored = []
    for s in sentences:
        tokens = re.findall(r"[a-záéíóúñüA-ZÁÉÍÓÚÑÜ]+", s.lower())
        score = sum(freq.get(t, 0) for t in tokens)
        scored.append((score, s))

    top = [s for _, s in sorted(scored, key=lambda x: x[0], reverse=True)[:max_sentences]]
    top_set = set(top)
    ordered = [s for s in sentences if s in top_set]
    return " ".join(ordered)


# ----------------- TRADUCCIÓN -----------------

def translate_summary(text: str, target_langs: List[str]) -> Dict[str, str]:
    """Traduce el texto a múltiples idiomas (googletrans)."""
    if not text.strip():
        return {}
    tr = Translator()
    out: Dict[str, str] = {}
    for lang in target_langs:
        try:
            out[lang] = tr.translate(text, dest=lang).text
        except Exception:
            out[lang] = ""
    return out


def translate_segments(segments: List[Dict], target_lang: str) -> List[Dict]:
    """
    Traduce cada segmento a 'target_lang' preservando tiempos.
    Útil para generar WebVTT traducido que se sincroniza con el video.
    """
    tr = Translator()
    out: List[Dict] = []
    for seg in segments:
        txt = seg["text"]
        try:
            ttxt = tr.translate(txt, dest=target_lang).text
        except Exception:
            ttxt = txt  # si falla, dejamos original
        out.append({"start": seg["start"], "end": seg["end"], "text": ttxt})
    return out


# ----------------- GUARDAR/CARGAR SEGMENTOS -----------------

def save_segments(segments: List[Dict], path: Path) -> None:
    path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")


def load_segments(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------- TTS -----------------

def _pick_voice_id_for_lang(engine, lang: str):
    tokens_map = {
        "es": ["es", "spanish", "es-es", "mex", "arg"],
        "en": ["en", "english", "en-us", "en-gb"],
        "pt": ["pt", "portuguese", "pt-br", "brasil"],
        "it": ["it", "italian"],
        "fr": ["fr", "french", "fr-fr"],
    }
    tokens = tokens_map.get(lang, [])
    for v in engine.getProperty("voices"):
        hay = f"{v.id} {getattr(v, 'name', '')}".lower()
        if any(t in hay for t in tokens):
            return v.id
    return None


def _tts_pyttsx3(text: str, out_path: Path, lang: str) -> Path:
    engine = pyttsx3.init()
    vid = _pick_voice_id_for_lang(engine, lang)
    if vid:
        engine.setProperty("voice", vid)
    engine.setProperty("rate", 180)
    engine.setProperty("volume", 1.0)
    out_wav = out_path.with_suffix(".wav")
    engine.save_to_file(text, str(out_wav))
    engine.runAndWait()
    return out_wav


def tts_synthesize(text: str, out_path: Path, lang: str = "es") -> Path:
    """
    Genera audio del texto en el idioma solicitado.
    Intenta gTTS (.mp3) y si falla usa pyttsx3 (.wav).
    """
    try:
        out_mp3 = out_path.with_suffix(".mp3")
        tts = gTTS(text=text, lang=(lang if lang in {"es", "en", "pt", "it", "fr"} else "es"))
        tts.save(str(out_mp3))
        return out_mp3
    except Exception:
        return _tts_pyttsx3(text, out_path, lang)
