"""Voz AIOS: TTS (hablar) y STT (escuchar), local y cloud.

Config (config.yaml):
  voice:
    tts: off | espeak | gemini | openai
    stt: off | vosk  | gemini | openai
    tts_lang: auto | es | en | fr | de | it | pt

Claves (en ~/.aios/.env, cargadas por chat.py a os.environ):
  GOOGLE_API_KEY  (gemini)
  OPENAI_API_KEY  (openai)
"""
import os
import json
import base64
import subprocess
import threading
import urllib.request

_LANGS = ("es", "fr", "de", "it", "pt", "en")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _skip_code(text):
    """Quita bloques de código/comandos y tablas para no deletrearlos."""
    lines = []
    in_code = False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if s.startswith(("$ ", "# ", "sudo ", "apt ", "dnf ", "pacman ", "sven ",
                         "git ", "curl ", "wget ", "systemctl ", "ssh ", "scp ")):
            continue
        if s.startswith(("|", "+", "-")) and ("|" in s or s.startswith("---")):
            continue  # tablas markdown
        lines.append(s)
    return " ".join(lines).strip()


def _detect_lang(text):
    """Idioma por marcas tipográficas (default en)."""
    if any(c in text for c in "ñáéíóú¿¡"):
        return "es"
    if any(c in text for c in "àâçèêëîïôùûüœ"):
        return "fr"
    if any(c in text for c in "äöüß"):
        return "de"
    if any(c in text for c in "àèéìòù"):
        return "it"
    if any(c in text for c in "ãõçâêô"):
        return "pt"
    return "en"


def _espeak_lang(lang):
    return lang if lang in _LANGS else "en"


def _play_pcm(pcm, rate=24000):
    if not pcm:
        return
    p = subprocess.Popen(["aplay", "-q", "-f", "S16_LE", "-r", str(rate), "-c", "1"],
                         stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p.communicate(pcm)


# ---------------------------------------------------------------------------
# TTS (hablar)
# ---------------------------------------------------------------------------

def speak(text, config):
    """Habla el texto con el motor TTS configurado (en hilo, no bloquea el chat)."""
    voice = config.get("voice", {}) if isinstance(config, dict) else {}
    tts = voice.get("tts", "off")
    if tts in (None, "off"):
        return
    clean = _skip_code(text)
    if not clean:
        return
    lang = voice.get("tts_lang", "auto")
    if lang == "auto":
        lang = _detect_lang(clean)
    threading.Thread(target=_speak_sync, args=(tts, clean, lang), daemon=True).start()


def _speak_sync(tts, text, lang):
    try:
        if tts == "espeak":
            _espeak(text, lang)
        elif tts == "gemini":
            _gemini_tts(text, lang)
        elif tts == "openai":
            _openai_tts(text, lang)
    except Exception:
        pass  # la voz nunca debe romper el chat


def _espeak(text, lang):
    v = _espeak_lang(lang)
    p1 = subprocess.Popen(["espeak-ng", "-v", v, "--stdout", text],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        subprocess.run(["aplay", "-q"], stdin=p1.stdout, stderr=subprocess.DEVNULL)
    finally:
        if p1.stdout:
            p1.stdout.close()
        p1.wait()


def _gemini_tts(text, lang):
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash-tts:generateContent?key=" + key)
    body = json.dumps({
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"]},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    _play_pcm(base64.b64decode(b64), rate=24000)


def _openai_tts(text, lang):
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return
    url = "https://api.openai.com/v1/audio/speech"
    body = json.dumps({"model": "gpt-4o-mini-tts", "voice": "alloy", "input": text}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        mp3 = r.read()
    p = subprocess.Popen(["ffmpeg", "-i", "pipe:0", "-f", "s16le", "-ar", "24000",
                          "-ac", "1", "pipe:1"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    pcm, _ = p.communicate(mp3)
    _play_pcm(pcm, rate=24000)


# ---------------------------------------------------------------------------
# STT (escuchar)
# ---------------------------------------------------------------------------

def listen(config):
    """Graba un mensaje con el micro y lo transcribe. Devuelve el texto o None."""
    voice = config.get("voice", {}) if isinstance(config, dict) else {}
    stt = voice.get("stt", "off")
    if stt in (None, "off"):
        return None
    wav = "/tmp/aios-mic.wav"
    try:
        subprocess.run(["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1",
                        "-d", "6", wav], stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        return None
    if not os.path.exists(wav):
        return None
    try:
        if stt == "vosk":
            return _vosk_stt(wav)
        if stt == "gemini":
            return _gemini_stt(wav)
        if stt == "openai":
            return _openai_stt(wav)
    except Exception:
        return None
    return None


def _vosk_stt(wav):
    import json as _json
    try:
        from vosk import Model, KaldiRecognizer
    except Exception:
        return None
    model_path = "/usr/local/share/aios/vosk-model-es"
    if not os.path.isdir(model_path):
        model_path = "/usr/local/share/aios/vosk-model"
    if not os.path.isdir(model_path):
        return None
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    with open(wav, "rb") as f:
        f.read(44)  # saltar cabecera WAV
        while True:
            chunk = f.read(4000)
            if not chunk:
                break
            rec.AcceptWaveform(chunk)
    res = _json.loads(rec.FinalResult())
    text = (res.get("text") or "").strip()
    return text or None


def _gemini_stt(wav):
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return None
    with open(wav, "rb") as f:
        audio = base64.b64encode(f.read()).decode()
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash:generateContent?key=" + key)
    body = json.dumps({
        "contents": [{"parts": [
            {"text": "Transcribe the audio exactly."},
            {"inlineData": {"mimeType": "audio/wav", "data": audio}},
        ]}],
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return (data["candidates"][0]["content"]["parts"][0].get("text") or "").strip() or None


def _openai_stt(wav):
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    boundary = "aiosboundary"
    with open(wav, "rb") as f:
        audio = f.read()
    body = (b"--" + boundary.encode() + b"\r\n"
            b'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'
            b"--" + boundary.encode() + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="a.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n" + audio + b"\r\n"
            b"--" + boundary.encode() + b"--\r\n")
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions",
                                 data=body, headers={
                                     "Authorization": "Bearer " + key,
                                     "Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return (data.get("text") or "").strip() or None
