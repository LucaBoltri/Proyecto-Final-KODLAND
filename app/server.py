from pathlib import Path
import uuid
from typing import Optional, List, Dict  # ⬅️ usar typing en Py3.9

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    redirect,
    url_for,
)

from pipeline import (
    extract_audio,
    transcribe,
    write_srt,
    write_vtt,
    summarize,
    tts_synthesize,
    translate_summary,
    translate_segments,
    save_segments,
    load_segments,
)

APP_ROOT   = Path(__file__).resolve().parents[1]
TEMP_DIR   = APP_ROOT / "data" / "temp"
OUTPUTS_DIR= APP_ROOT / "data" / "outputs"
VIDEOS_DIR = APP_ROOT / "data" / "videos"
AUDIO_DIR  = APP_ROOT / "data" / "audio"

LANG_LABEL: Dict[str, str] = {
    "es": "Español",
    "en": "English",
    "pt": "Português",
    "it": "Italiano",
    "fr": "Français",
}

app = Flask(__name__, template_folder="templates", static_folder="static")


def _existing_sub_langs(file_id: str, base_lang: Optional[str]) -> List[str]:
    """Retorna lista de códigos de idiomas para los que YA hay VTT."""
    langs = set()
    if base_lang:
        langs.add(base_lang)
    for p in OUTPUTS_DIR.glob(f"subs_{file_id}_*.vtt"):
        code = p.stem.split("_")[-1]
        langs.add(code)
    return sorted(langs)


def _tracks_payload(file_id: str, base_lang: Optional[str]) -> List[Dict]:
    """
    Arma la lista de pistas para <video>, con etiquetas cortas (solo el idioma).
    base_lang es el idioma del audio (o None/autodetect→'es' como fallback visual).
    """
    tracks: List[Dict] = []
    srclang = base_lang if (base_lang in LANG_LABEL) else "es"

    # pista base (subs_<id>.vtt)
    base_vtt = OUTPUTS_DIR / f"subs_{file_id}.vtt"
    if base_vtt.exists():
        tracks.append({
            "lang": srclang,
            "label": LANG_LABEL.get(srclang, srclang),
            "url": f"/outputs/{base_vtt.name}",
            "default": True
        })

    # pistas traducidas que existan
    for p in sorted(OUTPUTS_DIR.glob(f"subs_{file_id}_*.vtt")):
        code = p.stem.split("_")[-1]
        tracks.append({
            "lang": code,
            "label": LANG_LABEL.get(code, code),
            "url": f"/outputs/{p.name}",
            "default": False
        })
    return tracks


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    audio_lang   = request.form.get("lang", "auto")
    summary_lang = request.form.get("summary_lang", "orig")

    if not f:
        return render_template("index.html", message="No se recibió archivo.")

    for d in (TEMP_DIR, OUTPUTS_DIR, VIDEOS_DIR, AUDIO_DIR):
        d.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:8]
    ext = Path(f.filename).suffix.lower() or ".mp4"

    tmp_in = TEMP_DIR / f"input_{uid}{ext}"
    f.save(tmp_in)
    video_path = VIDEOS_DIR / f"video_{uid}{ext}"
    tmp_in.replace(video_path)

    # Audio + ASR
    audio_path = extract_audio(video_path)
    language = None if audio_lang == "auto" else audio_lang
    segments = transcribe(audio_path, language=language)

    # Guardar segmentos JSON
    seg_json = OUTPUTS_DIR / f"segments_{uid}.json"
    save_segments(segments, seg_json)

    # SRT + VTT base
    srt_path = OUTPUTS_DIR / f"subs_{uid}.srt"
    vtt_path = OUTPUTS_DIR / f"subs_{uid}.vtt"
    write_srt(segments, srt_path)
    write_vtt(segments, vtt_path)

    # Resumen (con posible traducción de salida)
    full_text = " ".join(s["text"] for s in segments)
    base_summary = summarize(full_text)

    display_summary = base_summary
    chosen_summary_lang = audio_lang if audio_lang in LANG_LABEL else "es"
    if summary_lang in LANG_LABEL:
        trans = translate_summary(base_summary, [summary_lang])
        translated = trans.get(summary_lang, "").strip()
        if translated:
            display_summary = translated
            chosen_summary_lang = summary_lang

    # TTS del resumen mostrado
    audio_out = AUDIO_DIR / f"summary_{uid}"
    tts_path = tts_synthesize(display_summary, audio_out, lang=chosen_summary_lang)
    summary_audio_url = f"/audio/{tts_path.name}"

    # Guardar resumen textual
    (OUTPUTS_DIR / f"summary_{uid}.txt").write_text(display_summary, encoding="utf-8")

    # URLs base
    srt_url   = f"/outputs/subs_{uid}.srt"
    vtt_url   = f"/outputs/subs_{uid}.vtt"
    video_url = f"/videos/{video_path.name}"
    txt_url   = f"/outputs/summary_{uid}.txt"

    existing_subs = _existing_sub_langs(uid, audio_lang if audio_lang in LANG_LABEL else None)
    tracks = _tracks_payload(uid, audio_lang if audio_lang in LANG_LABEL else None)

    return render_template(
        "index.html",
        message="Archivo recibido y transcrito",
        file_id=uid,
        used_language=audio_lang,
        summary_lang=summary_lang,
        preview=segments[:3],
        summary=display_summary,
        srt_url=srt_url,
        vtt_url=vtt_url,
        video_url=video_url,
        summary_audio_url=summary_audio_url,
        tracks=tracks,
        txt_url=txt_url,
        existing_subs=existing_subs,
        LANG_LABEL=LANG_LABEL,
    )


@app.route("/translate", methods=["POST"])
def translate_route():
    file_id = request.form.get("file_id")
    target  = request.form.get("target_lang")
    if not file_id or not target:
        return redirect(url_for("home"))

    txt_path = OUTPUTS_DIR / f"summary_{file_id}.txt"
    if not txt_path.exists():
        return redirect(url_for("home"))

    base_summary = txt_path.read_text(encoding="utf-8").strip()
    trans = translate_summary(base_summary, [target])
    translated = trans.get(target, "").strip() or base_summary

    audio_out = AUDIO_DIR / f"summary_{file_id}_{target}"
    tts_audio_path = tts_synthesize(translated, audio_out, lang=target)
    summary_audio_url = f"/audio/{tts_audio_path.name}"

    srt_url   = f"/outputs/subs_{file_id}.srt"
    vtt_url   = f"/outputs/subs_{file_id}.vtt"
    video_file= next(VIDEOS_DIR.glob(f"video_{file_id}.*"), None)
    video_url = f"/videos/{video_file.name}" if video_file else None

    tracks = _tracks_payload(file_id, None)
    existing_subs = _existing_sub_langs(file_id, None)

    return render_template(
        "index.html",
        message=f"Traducción a {LANG_LABEL.get(target, target)} lista",
        file_id=file_id,
        used_language="auto",
        summary_lang=target,
        preview=None,
        summary=translated,
        srt_url=srt_url,
        vtt_url=vtt_url,
        video_url=video_url,
        summary_audio_url=summary_audio_url,
        tracks=tracks,
        txt_url=f"/outputs/summary_{file_id}.txt",
        existing_subs=existing_subs,
        LANG_LABEL=LANG_LABEL,
    )


@app.route("/translate_subs", methods=["POST"])
def translate_subs_route():
    file_id = request.form.get("file_id")
    lang    = request.form.get("subs_lang")
    if not file_id or lang not in LANG_LABEL:
        return redirect(url_for("home"))

    seg_json = OUTPUTS_DIR / f"segments_{file_id}.json"
    if not seg_json.exists():
        return redirect(url_for("home"))

    vtt_t_path = OUTPUTS_DIR / f"subs_{file_id}_{lang}.vtt"
    if vtt_t_path.exists():
        msg = f"La pista de subtítulos en {LANG_LABEL[lang]} ya existe."
    else:
        segments = load_segments(seg_json)
        t_segments = translate_segments(segments, lang)
        write_vtt(t_segments, vtt_t_path)
        msg = f"Pista {LANG_LABEL[lang]} generada."

    srt_url   = f"/outputs/subs_{file_id}.srt"
    vtt_url   = f"/outputs/subs_{file_id}.vtt"
    video_file= next(VIDEOS_DIR.glob(f"video_{file_id}.*"), None)
    video_url = f"/videos/{video_file.name}" if video_file else None

    summary_txt = OUTPUTS_DIR / f"summary_{file_id}.txt"
    summary = summary_txt.read_text(encoding="utf-8").strip() if summary_txt.exists() else ""
    audio_any = next(AUDIO_DIR.glob(f"summary_{file_id}*.*"), None)
    summary_audio_url = f"/audio/{audio_any.name}" if audio_any else None

    tracks = _tracks_payload(file_id, None)
    existing_subs = _existing_sub_langs(file_id, None)

    return render_template(
        "index.html",
        message=msg,
        file_id=file_id,
        used_language="auto",
        summary_lang="orig",
        preview=None,
        summary=summary,
        srt_url=srt_url,
        vtt_url=vtt_url,
        video_url=video_url,
        summary_audio_url=summary_audio_url,
        tracks=tracks,
        txt_url=f"/outputs/summary_{file_id}.txt",
        existing_subs=existing_subs,
        LANG_LABEL=LANG_LABEL,
    )


@app.route("/outputs/<path:filename>")
def get_output(filename):
    return send_from_directory(OUTPUTS_DIR, filename, as_attachment=True)

@app.route("/videos/<path:filename>")
def get_video(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=False)

@app.route("/audio/<path:filename>")
def get_audio(filename):
    return send_from_directory(AUDIO_DIR, filename, as_attachment=False)


if __name__ == "__main__":
    app.run(debug=True)
