"""AIOS voice: TTS (speak) and STT (listen), local and cloud.

Config (config.yaml):
  voice:
    tts: off | espeak | gemini | openai
    stt: off | vosk  | gemini | openai
    tts_lang: auto | es | en | fr | de | it | pt

Keys (in ~/.aios/.env, loaded by chat.py into os.environ):
  GOOGLE_API_KEY  (gemini)
  OPENAI_API_KEY  (openai)
"""
import os
import json
import base64
import subprocess
import threading
import queue
import urllib.request

_PROCS = []
_LOCK = threading.Lock()


def _log(msg):
    try:
        with open("/tmp/aios-voice.log", "a") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def _track(p):
    with _LOCK:
        _PROCS.append(p)


def stop():
    """Interrupt current voice (kills active espeak-ng/aplay)."""
    with _LOCK:
        procs = list(_PROCS)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    with _LOCK:
        _PROCS.clear()

_LANGS = ("es", "fr", "de", "it", "pt", "en", "ca")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _skip_code(text):
    """Remove code/command blocks and tables so they are not spelled out."""
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
            continue  # markdown tables
        lines.append(s)
    return " ".join(lines).strip()


def _detect_lang(text):
    """Language by typographical marks (default en)."""
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
    _track(p)
    p.communicate(pcm)


# ---------------------------------------------------------------------------
# TTS (speak)
# ---------------------------------------------------------------------------

def speak(text, config):
    """Speak the text with the configured TTS engine (in a thread, does not block chat)."""
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


def _render(tts, text, lang):
    """Speak ONE sentence with the given engine. Does not stop() nor touch the
    tic aplay: the caller owns those (so a whole turn closes/reopens it once)."""
    if tts == "live":
        # Live API (native audio). Fall back if it cannot run.
        if not _live_tts(text, lang):
            _espeak(text, lang)
    elif tts == "espeak":
        _espeak(text, lang)
    elif tts == "gemini":
        _gemini_tts(text, lang)
    elif tts == "openai":
        _openai_tts(text, lang)


def _speak_sync(tts, text, lang):
    try:
        stop()
        # Free the PCM device held by the tic aplay, then restore it after.
        try:
            import agent
            agent._close_audio()
        except Exception as e:
            _log(f"close_audio error: {e}")
        try:
            _render(tts, text, lang)
        finally:
            try:
                import agent
                agent._reopen_audio()
            except Exception as e:
                _log(f"reopen_audio error: {e}")
    except Exception as e:
        _log(f"speak_sync error: {e}")
        pass  # voice must never break the chat


# ---------------------------------------------------------------------------
# Sentence streaming: speak WHILE the reply is still being written.
#
# chat.py used to call speak(response) once the whole reply was ready, and the
# engines buffer all their audio, so nothing was heard until the end. Measured
# 14 Sep 2026: 7.47 s of silence after the text was complete, on top of 23.87 s
# spent waiting for the first character. Feeding whole sentences as they arrive
# makes the first words audible in a second or two.
#
# One worker thread drains a queue, so sentences never overlap, and the tic
# aplay is closed/reopened ONCE per turn (not once per sentence). A generation
# counter lets a new turn abandon the previous one (barge-in).
# ---------------------------------------------------------------------------

_SENT_END = (". ", "! ", "? ", ".\n", "!\n", "?\n", "\u2026 ", "\n\n")

_NARR = {"gen": 0, "q": None, "buf": "", "in_code": False, "tts": None, "lang": None}


def _strip_md(text):
    """Remove light markdown so no TTS reads asterisks or backticks."""
    import re as _re
    text = _re.sub(r"`([^`]*)`", r"\1", text)          # inline code
    text = _re.sub(r"\*\*([^*]+)\*\*", r"\1", text)    # bold
    text = _re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)  # italics
    text = _re.sub(r"^\s*#{1,6}\s*", "", text, flags=_re.M)  # headings
    text = _re.sub(r"^\s*[-*+]\s+", "", text, flags=_re.M)   # bullets
    text = _re.sub(r"^\s*\d+[.)]\s+", "", text, flags=_re.M)  # numbered lists
    text = _re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # links
    text = text.replace("|", " ").replace("_", " ")         # tables / emphasis
    return text


def _find_cut(text, start):
    """Index just past the first sentence delimiter at/after start (-1 if none)."""
    best = -1
    for d in _SENT_END:
        k = text.find(d, start)
        if k >= 0:
            end = k + len(d)
            if best < 0 or end < best:
                best = end
    return best


def stream_begin(config):
    """Start narrating sentence by sentence. Returns True if the narrator is on."""
    voice = config.get("voice", {}) if isinstance(config, dict) else {}
    tts = voice.get("tts", "off")
    if tts in (None, "off"):
        return False
    stop()                       # cut anything still sounding (barge-in)
    _NARR["gen"] += 1
    gen = _NARR["gen"]
    _NARR["q"] = queue.Queue()
    _NARR["buf"] = ""
    _NARR["in_code"] = False
    _NARR["tts"] = tts
    _NARR["lang"] = voice.get("tts_lang", "auto")
    threading.Thread(target=_narrator, args=(gen, tts, _NARR["lang"]), daemon=True).start()
    return True


def _narrator(gen, tts, lang):
    """Drain the sentence queue, one at a time, holding the PCM device."""
    q = _NARR.get("q")
    try:
        import agent
        agent._close_audio()     # once per turn, not once per sentence
    except Exception as e:
        _log(f"narrator close_audio: {e}")
    try:
        while True:
            frase = q.get()
            if frase is None:
                break
            if _NARR.get("gen") != gen:
                break            # a newer turn took over (barge-in)
            if not frase.strip():
                continue
            l = _detect_lang(frase) if lang == "auto" else lang
            try:
                _render(tts, frase, l)
            except Exception as e:
                _log(f"narrator render: {e}")
    except Exception as e:
        _log(f"narrator error: {e}")
    finally:
        if _NARR.get("gen") == gen:
            try:
                import agent
                agent._reopen_audio()
            except Exception as e:
                _log(f"narrator reopen_audio: {e}")


def stream_feed(chunk):
    """Feed a stream chunk: queue every complete sentence it completes."""
    q = _NARR.get("q")
    if q is None or not chunk:
        return
    txt = _NARR["buf"] + chunk
    listas, i, n = [], 0, len(txt)
    while i < n:
        if txt.startswith("```", i):
            _NARR["in_code"] = not _NARR["in_code"]
            i += 3
            continue
        if _NARR["in_code"]:
            i += 1               # inside a code block: never spoken
            continue
        corte = _find_cut(txt, i)
        if corte < 0:
            break
        listas.append(txt[i:corte])
        i = corte
    _NARR["buf"] = txt[i:]
    for f in listas:
        f = _strip_md(f).strip()
        if f:
            q.put(f)


def stream_end():
    """Flush the trailing text and tell the narrator there is no more."""
    q = _NARR.get("q")
    if q is None:
        return
    resto = _strip_md(_NARR["buf"]).strip()
    if resto:
        q.put(resto)
    _NARR["buf"] = ""
    _NARR["q"] = None
    q.put(None)                  # sentinel: the worker exits (and reopens audio)


# ---------------------------------------------------------------------------
# Gemini Live API: audio-a-audio por WebSocket.
#
# Distinto de _gemini_tts: aquel es generateContent (texto -> audio) y sufre un
# limite de ~10 peticiones/minuto. Este abre una sesion Live (wss://.../
# BidiGenerateContent) y devuelve AUDIO NATIVO. Medido: conecta, responde con
# PCM a 24 kHz, y el tier gratuito lo da "Free of charge".
#
# Se usa como motor de SALIDA: se le manda el texto que el agente ya ha escrito
# y se reproduce el audio que devuelve. (El Live puede conversar por su cuenta,
# pero como motor de voz del chat lo que queremos es que HABLE lo que se escribio.)
#
# Requiere el modulo `websockets` (no esta en el arbol de la ISO por defecto:
# sven install python-websockets).
# ---------------------------------------------------------------------------
LIVE_MODEL = "gemini-3.1-flash-live-preview"
LIVE_URL = ("wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")


def _live_tts(text, lang):
    """Synthesise with the Gemini Live API (WebSocket, native audio).

    Returns True if it spoke, False to let another engine do it.
    """
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        _log("live: no GOOGLE_API_KEY; falling back")
        return False
    try:
        import asyncio
        import base64
        import json as _json
        import websockets
    except ImportError as e:
        _log(f"live: missing dependency ({e}); falling back")
        return False

    async def _run():
        pcm = bytearray()
        async with websockets.connect(LIVE_URL + "?key=" + key,
                                      open_timeout=30, close_timeout=5) as ws:
            await ws.send(_json.dumps({
                "setup": {
                    "model": "models/" + LIVE_MODEL,
                    "generationConfig": {"responseModalities": ["AUDIO"]},
                }
            }))
            # esperar setupComplete antes de mandar nada
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")
            if "setupComplete" not in raw:
                _log(f"live: unexpected setup reply: {raw[:200]}")
                return b""
            await ws.send(_json.dumps({
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": text}]}],
                    "turnComplete": True,
                }
            }))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=20)
                except asyncio.TimeoutError:
                    break
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "replace")
                msg = _json.loads(raw)
                sc = msg.get("serverContent", {})
                for part in sc.get("modelTurn", {}).get("parts", []):
                    data = part.get("inlineData", {}).get("data")
                    if data:
                        pcm.extend(base64.b64decode(data))
                if sc.get("turnComplete"):
                    break
        return bytes(pcm)

    try:
        audio = asyncio.run(_run())
    except Exception as e:
        _log(f"live: error: {e}")
        return False
    if not audio:
        _log("live: no audio returned; falling back")
        return False
    _play_pcm(audio, rate=24000)   # el Live devuelve PCM 16-bit a 24 kHz
    return True


def _espeak(text, lang):
    v = _espeak_lang(lang)
    p1 = subprocess.Popen(["espeak-ng", "-v", v, "--stdout", text],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    _track(p1)
    p2 = subprocess.Popen(["aplay", "-q"], stdin=p1.stdout, stderr=subprocess.DEVNULL)
    _track(p2)
    try:
        p2.wait()
    finally:
        if p1.stdout:
            p1.stdout.close()
        p1.wait()


def _gemini_tts(text, lang):
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash-preview-tts:generateContent?key=" + key)
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
# STT (listen)
# ---------------------------------------------------------------------------

def listen(config):
    """Record a message with the microphone and transcribe it. Returns the text or None."""
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
    # One model per language: /usr/local/share/aios/vosk-model-<lang>.
    # The language comes from voice.stt_lang (config.yaml); "es" is the fallback
    # so a config without the key keeps working.
    lang = (voice.get("stt_lang") or "es") if isinstance(voice, dict) else "es"
    if lang not in _LANGS:
        lang = "es"
    candidates = [
        f"/usr/local/share/aios/vosk-model-{lang}",
        f"/usr/local/share/aios/vosk-model-{lang}-small",
    ]
    if lang == "es":
        # legacy: before the multi-language support only Spanish shipped, under
        # this unnamed path. It IS a Spanish model, so reusing it for "es" is
        # correct -- but never for another language (that would transcribe
        # French with a Spanish model and silently return nonsense).
        candidates.append("/usr/local/share/aios/vosk-model")
    model_path = next((p for p in candidates if os.path.isdir(p)), None)
    if not model_path:
        _log(f"_vosk_stt: no model for lang={lang!r}; looked in: {candidates}")
        return None
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    with open(wav, "rb") as f:
        f.read(44)  # skip WAV header
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
