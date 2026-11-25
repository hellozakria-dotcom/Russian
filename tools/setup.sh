#!/usr/bin/env bash
# One-time setup for tools/build.py: Russian voice (Piper) + SVG renderer.
set -e
cd "$(dirname "$0")"
pip install piper-tts cairosvg numpy pillow 2>/dev/null || pip install --break-system-packages piper-tts cairosvg numpy pillow
mkdir -p voice
if [ ! -f voice/ru-irinia-medium.onnx ]; then
  curl -sL -o voice/v.tgz https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-ru-irinia-medium.tar.gz
  tar xzf voice/v.tgz -C voice && rm voice/v.tgz
fi
command -v ffmpeg >/dev/null || echo "Also install ffmpeg (needed to make mp3 files)."
echo "Ready: python3 tools/build.py"
