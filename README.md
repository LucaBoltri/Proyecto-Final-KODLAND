# Proyecto Final KODLAND 🎬📝

Aplicación web que permite:

- Subir un video y extraer su audio.
- Generar subtítulos automáticos con **Faster Whisper**.
- Exportar subtítulos en formato `.srt` y `.vtt`.
- Generar resúmenes de lo hablado en el video.
- Escuchar el resumen con **síntesis de voz (TTS)**.
- Traducir tanto el resumen como los subtítulos a varios idiomas (es, en, pt, it, fr).
- Descargar los resultados en distintos formatos.

## Tecnologías utilizadas
- Python 3 + Flask
- Faster Whisper (Whisper optimizado)
- FFmpeg
- gTTS + pyttsx3 (Text to Speech)
- Googletrans (traducción)
- HTML + CSS (frontend básico)
- GitHub para control de versiones

## Cómo correrlo en local
```bash
# Clonar el repo
git clone https://github.com/LucaBoltri/Proyecto-Final-KODLAND.git
cd Proyecto-Final-KODLAND

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate   # en Windows
source venv/bin/activate  # en Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el servidor
python app/server.py
