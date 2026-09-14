#!/usr/bin/env python3
"""Puente con la Gemini Live API: el modelo responde HABLANDO y da su transcripcion.

DISENO (Carlos, 14 Sep 2026): es un CAMINO NUEVO que se ANADE. No sustituye nada.
  - Solo se usa cuando el usuario elige `gemini-live` en el menu /voice.
  - Los otros motores (espeak, gemini, openai) siguen con el camino de siempre
    (LLM del usuario -> texto -> narrador -> speak()). Nada de eso se toca.

Por que existe: `gemini-live` NO es un TTS, es un LLM completo
(gemini-3.1-flash-live-preview: 131k entrada, 65k salida, function calling,
97 idiomas). Con el seleccionado, el Live ES el modelo: recibe el prompt,
razona, ejecuta tools y responde hablando. El texto de pantalla sale de su
transcripcion de salida, asi que VOZ Y TEXTO son el mismo contenido.
"""
import asyncio
import base64
import json
import os

MODEL = "gemini-3.1-flash-live-preview"
URL = ("wss://generativelanguage.googleapis.com/ws/"
       "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")


def _log(msg):
    try:
        with open("/tmp/aios-gemini-live.log", "a", encoding="utf-8") as f:
            import time
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def _log_reset():
    try:
        open("/tmp/aios-gemini-live.log", "w").close()
    except Exception:
        pass


def available():
    """True if we can use it: module present, key present, websockets installed."""
    if not os.environ.get("GOOGLE_API_KEY"):
        return False, "no GOOGLE_API_KEY"
    try:
        import websockets  # noqa
    except ImportError:
        return False, "websockets not installed"
    return True, ""


def _schema(p):
    """Clean a JSON Schema for Gemini: it rejects $schema/additionalProperties."""
    if not isinstance(p, dict):
        return {"type": "string"}
    out = {}
    for k, v in p.items():
        if k in ("$schema", "additionalProperties", "title", "default", "examples"):
            continue
        if k == "properties" and isinstance(v, dict):
            out[k] = {pk: _schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _schema(v)
        else:
            out[k] = v
    if "type" not in out:
        out["type"] = "object" if "properties" in out else "string"
    return out


def _geminify(tools):
    """OpenAI tool schemas -> Gemini functionDeclarations."""
    decls = []
    for t in tools or []:
        fn = (t or {}).get("function") or {}
        if not fn.get("name"):
            continue
        d = {"name": fn["name"]}
        if fn.get("description"):
            d["description"] = fn["description"]
        params = fn.get("parameters")
        if params:
            d["parameters"] = _schema(params)
        decls.append(d)
    return [{"functionDeclarations": decls}] if decls else []


class Session:
    """One Gemini Live turn. Context lives in the caller (the agent's messages)."""

    def __init__(self, cfg):
        self.cfg = cfg or {}
        self.out_sink = None      # callable(text) -> print to screen
        self.audio = None         # callable(bytes) -> play
        self.on_audio_end = None

    async def _turn(self, prompt, system_prompt, tools, tool_runner,
                    tool_calls_box, transcript_box):
        key = os.environ.get("GOOGLE_API_KEY", "")
        pcm_total = 0
        setup = {
            "model": "models/" + MODEL,
            "generationConfig": {"responseModalities": ["AUDIO"]},
            # The transcript of what it SAYS: this is the on-screen text, and it
            # is by construction the same content as the audio.
            "outputAudioTranscription": {},
        }
        if system_prompt:
            setup["systemInstruction"] = {"parts": [{"text": system_prompt[:30000]}]}
        gt = _geminify(tools)
        if gt:
            setup["tools"] = gt

        async with self._ws_connect(key) as ws:
            await ws.send(json.dumps({"setup": setup}))
            raw = await asyncio.wait_for(ws.recv(), timeout=40)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")
            if "setupComplete" not in raw:
                _log(f"setup inesperado: {raw[:300]}")
                return pcm_total, transcript_box

            # 3.1: send_client_content is meant for seeding history; realtimeInput
            # is the documented way to send text mid-conversation.
            await ws.send(json.dumps({
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": prompt}]}],
                    "turnComplete": True,
                }
            }))

            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=90)
                except asyncio.TimeoutError:
                    _log("timeout esperando al modelo")
                    break
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "replace")
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if msg.get("toolCall"):
                    for fc in (msg["toolCall"].get("functionCalls") or []):
                        name = fc.get("name", "")
                        args = fc.get("args") or {}
                        _log(f"tool: {name} {str(args)[:160]}")
                        try:
                            res = tool_runner(name, args)
                        except Exception as e:
                            res = json.dumps({"error": str(e)[:200]})
                        tool_calls_box.append((name, args, res))
                        await ws.send(json.dumps({
                            "toolResponse": {"functionResponses": [{
                                "id": fc.get("id", ""),
                                "name": name,
                                "response": {"result": str(res)[:6000]},
                            }]}
                        }))
                    continue

                sc = msg.get("serverContent") or {}
                if sc.get("interrupted"):
                    _log("interrumpido por el usuario (barge-in nativo)")

                for part in ((sc.get("modelTurn") or {}).get("parts") or []):
                    data = (part.get("inlineData") or {}).get("data")
                    if data:
                        chunk = base64.b64decode(data)
                        pcm_total += len(chunk)
                        if self.audio:
                            self.audio(chunk)
                    txt = part.get("text")
                    if txt:
                        transcript_box.append(txt)
                        if self.out_sink:
                            self.out_sink(txt)

                ot = (sc.get("outputTranscription") or {}).get("text")
                if ot:
                    transcript_box.append(ot)
                    if self.out_sink:
                        self.out_sink(ot)

                if sc.get("turnComplete"):
                    break

            return pcm_total, transcript_box

    def _ws_connect(self, key):
        import websockets
        return websockets.connect(URL + "?key=" + key,
                                  open_timeout=30, close_timeout=5,
                                  max_size=None)


def run_turn(prompt, system_prompt=None, tools=None, tool_runner=None,
             out_sink=None, audio=None, audio_end=None, cfg=None):
    """One user turn against Gemini Live.

    Returns (ok, transcript, tool_calls, audio_bytes).
    Never raises: the caller falls back to the normal path if ok is False.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        _log("sin GOOGLE_API_KEY -> no se puede usar")
        return False, "", [], 0
    try:
        import websockets  # noqa
    except ImportError:
        _log("falta el modulo websockets")
        return False, "", [], 0

    s = Session(cfg)
    s.out_sink = out_sink
    s.audio = audio
    s.on_audio_end = audio_end
    tbox, cbox = [], []
    try:
        total, _ = asyncio.run(s._turn(prompt, system_prompt, tools, tool_runner,
                                       cbox, tbox))
        return True, "".join(tbox), cbox, total
    except Exception as e:
        _log(f"error en el turno: {type(e).__name__}: {str(e)[:300]}")
        return False, "".join(tbox), cbox, 0
