from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    abort,
    flash,
)

from app.pipeline import (
    extract_audio,
    transcribe,
    write_srt,
    write_vtt,
    summarize,
    translate_summary,
    translate_segments,
    tts_synthesize,
)

from googletrans import Translator


APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUTS_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"

for d in (DATA_DIR, VIDEOS_DIR, AUDIO_DIR, OUTPUTS_DIR, TEMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "videoconv-dev"


def _state_path(file_id: str) -> Path:
    return TEMP_DIR / f"state_{file_id}.json"


def load_state(file_id: str) -> dict:
    p = _state_path(file_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_state(file_id: str, data: dict) -> None:
    _state_path(file_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fmt_size(n_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(n_bytes)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.1f} {u}"
        size /= 1024.0


@app.route("/videos/<path:filename>")
def videos(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=False)


@app.route("/audio/<path:filename>")
def audio(filename):
    return send_from_directory(AUDIO_DIR, filename, as_attachment=False)


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(OUTPUTS_DIR, filename, as_attachment=False)


@app.get("/")
def home():
    return render_template("home.html")


@app.get("/upload")
def upload():
    return render_template("upload.html")


@app.post("/upload")
def do_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return render_template("upload.html", error="No se recibió archivo.")

    audio_lang = (request.form.get("audio_lang") or "auto").strip()
    summary_lang = (request.form.get("summary_lang") or "es").strip()

    uid = uuid.uuid4().hex[:8]
    ext = Path(f.filename).suffix.lower() or ".mp4"
    video_name = f"video_{uid}{ext}"
    video_path = VIDEOS_DIR / video_name
    f.save(video_path)

    try:
        audio_path = extract_audio(video_path)
        lang_for_whisper = None if audio_lang == "auto" else audio_lang
        segments = transcribe(audio_path, language=lang_for_whisper)

        # SRT base
        srt_name = f"subs_{uid}_base.srt"
        write_srt(segments, OUTPUTS_DIR / srt_name)

        # VTT base (para que el <video> ya tenga una pista)
        base_lang = audio_lang if audio_lang != "auto" else "es"
        vtt_base_name = f"subs_{uid}_{base_lang}.vtt"
        write_vtt(segments, OUTPUTS_DIR / vtt_base_name)
        tracks: Dict[str, str] = {base_lang: vtt_base_name}

        # Resumen
        full_text = " ".join(s["text"] for s in segments)
        base_summary = summarize(full_text)

        summary_text = base_summary
        if summary_lang != "es":
            try:
                tr = Translator()
                summary_text = tr.translate(base_summary, dest=summary_lang).text
            except Exception:
                pass

        # TTS versionado por idioma
        try:
            tts_base = AUDIO_DIR / f"summary_{uid}_{summary_lang}"
            final_audio = tts_synthesize(summary_text, tts_base, lang=summary_lang)
            summary_audio_name = final_audio.name
        except Exception:
            summary_audio_name = None

        txt_name = f"summary_{uid}.txt"
        (OUTPUTS_DIR / txt_name).write_text(summary_text, encoding="utf-8")

        st = {
            "file_id": uid,
            "video_name": video_name,
            "video_size": video_path.stat().st_size,
            "segments": segments,
            "summary": summary_text,
            "detected_lang": None,
            "used_language": audio_lang,        # puede ser "auto"
            "summary_lang": summary_lang,
            "tracks": tracks,                   # << ya hay al menos una pista
            "srt_base": srt_name,
            "summary_txt": txt_name,
            "summary_audio": summary_audio_name,
        }
        save_state(uid, st)
    except Exception as e:
        return render_template("upload.html", error=f"Procesamiento falló: {e}")

    return redirect(url_for("workspace", file_id=uid))


@app.get("/workspace/<file_id>")
def workspace(file_id: str):
    st = load_state(file_id)
    if not st:
        abort(404)

    video_name = st.get("video_name")
    video_url = url_for("videos", filename=video_name) if video_name else None

    srt_url = url_for("outputs", filename=st["srt_base"]) if st.get("srt_base") else None
    txt_url = url_for("outputs", filename=st["summary_txt"]) if st.get("summary_txt") else None

    summary_audio_url = None
    if st.get("summary_audio"):
        summary_audio_url = url_for("audio", filename=st["summary_audio"]) + f"?v={uuid.uuid4().hex[:6]}"

    tracks = st.get("tracks", {})
    tracks_urls = {lang: url_for("outputs", filename=fn) for lang, fn in tracks.items()}
    existing_tracks = list(tracks.keys())

    size_human = _fmt_size((VIDEOS_DIR / video_name).stat().st_size) if video_name else None

    return render_template(
        "workspace.html",
        file_id=file_id,
        filename=video_name,
        duration=None,
        size_human=size_human,
        video_url=video_url,
        detected_lang=st.get("detected_lang") or "auto",
        used_language=st.get("used_language") or "auto",
        summary=st.get("summary"),
        summary_lang=st.get("summary_lang") or "es",
        summary_audio_url=summary_audio_url,
        srt_url=srt_url,
        txt_url=txt_url,
        existing_tracks=existing_tracks,
        tracks=tracks_urls,     # << urls para inyectar <track>
    )


@app.post("/set_lang/<file_id>")
def set_lang(file_id: str):
    st = load_state(file_id)
    if not st:
        abort(404)

    new_lang = (request.form.get("lang") or "auto").strip()
    st["used_language"] = new_lang
    save_state(file_id, st)
    return redirect(url_for("workspace", file_id=file_id))


@app.post("/summary/<file_id>")
def summary(file_id: str):
    st = load_state(file_id)
    if not st:
        abort(404)

    sum_lang = (request.form.get("sum_lang") or "es").strip()
    st["summary_lang"] = sum_lang

    full_text = " ".join(s["text"] for s in st.get("segments", []))
    base_summary = summarize(full_text)

    summary_text = base_summary
    try:
        if sum_lang != "es":
            tr = Translator()
            summary_text = tr.translate(base_summary, dest=sum_lang).text
    except Exception:
        pass

    st["summary"] = summary_text

    try:
        tts_base = AUDIO_DIR / f"summary_{file_id}_{sum_lang}"
        final_audio = tts_synthesize(summary_text, tts_base, lang=sum_lang)
        st["summary_audio"] = final_audio.name
    except Exception:
        st["summary_audio"] = None

    txt_name = f"summary_{file_id}.txt"
    (OUTPUTS_DIR / txt_name).write_text(summary_text, encoding="utf-8")
    st["summary_txt"] = txt_name

    save_state(file_id, st)
    return redirect(url_for("workspace", file_id=file_id))


@app.post("/generate_tracks/<file_id>")
def generate_tracks(file_id: str):
    st = load_state(file_id)
    if not st:
        abort(404)

    # Ahora soportamos un solo <select name="lang"> O un getlist("langs") si quedara compat.
    selected = request.form.get("lang")
    langs = [selected] if selected else request.form.getlist("langs")
    langs = [l for l in langs if l]

    segments = st.get("segments", [])
    if not segments:
        flash("No hay segmentos para subtitular.", "warn")
        return redirect(url_for("workspace", file_id=file_id))

    tracks: Dict[str, str] = st.get("tracks", {})
    base_lang = (st.get("used_language") or "auto")
    if base_lang == "auto":
        base_lang = "es"

    for lang in langs:
        if not lang or lang in tracks:
            continue

        if lang == base_lang:
            target_segments = segments
        else:
            target_segments = translate_segments(segments, lang)

        vtt_name = f"subs_{file_id}_{lang}.vtt"
        write_vtt(target_segments, OUTPUTS_DIR / vtt_name)
        tracks[lang] = vtt_name

    st["tracks"] = tracks
    save_state(file_id, st)
    return redirect(url_for("workspace", file_id=file_id))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
