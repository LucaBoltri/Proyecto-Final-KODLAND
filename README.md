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

## Dependencias principales

El archivo `requierements.txt` incluye:

```
# Servidor
Flask>=3.0,<4.0

# ASR (Whisper acelerado)
faster-whisper>=0.10.0
ctranslate2>=4.3.1
tokenizers>=0.15.0
onnxruntime>=1.16.0
numpy>=1.23

# Traducción
googletrans==4.0.0rc1

# Texto a voz (TTS)
gTTS>=2.5.1
pyttsx3>=2.90

# Utilidades
requests>=2.31.0
```

## Estructura del proyecto

- `app/server.py`: Servidor Flask y rutas principales
- `app/pipeline.py`: Lógica de procesamiento (audio, transcripción, resumen, TTS, traducción)
- `app/templates/`: Plantillas HTML (Jinja2)
- `app/static/`: CSS y archivos estáticos
- `data/`: Videos, audios, subtítulos, resúmenes y archivos temporales

## Uso

1. Abre la app en tu navegador (`http://localhost:5000`).
2. Sube un video.
3. Elige idioma y genera resumen o subtítulos.
4. Descarga los resultados.

## Notas

- Todos los archivos generados se guardan en la carpeta `data/`.
- Los subtítulos se exportan en `.srt` y `.vtt`.
- Los resúmenes pueden descargarse en `.txt` y `.mp3`.
- El frontend es minimalista, la lógica está en Python.

---
Proyecto realizado para Kodland. Uso educativo.
