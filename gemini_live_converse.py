"""Conversacion natural con Gemini Live: hablan los dos.

Con `gemini-live` NO se usan `/mic` ni `Ctrl+G`: el Live mantiene una sesion
bidireccional, oye el micro y responde hablando. El prompt de texto sigue
disponible porque el usuario puede querer escribir.

MEDIDO (14 Sep 2026, en el portatil):
  - La VAD AUTOMATICA del servidor NO detecta el habla enviada por trozos:
    4 mensajes, 0 audio, no responde.
  - La VAD MANUAL SI funciona: activityStart -> audio -> activityEnd devolvio
    "OYO: Hola, dime quien eres" -> "DIJO: ...", 4,29 s de audio, primer audio
    a los 3,18 s.
  => Se usa VAD LOCAL (energia) para decidir activityStart/activityEnd.

Formato (doc oficial de la Live API, WebSockets):
  setup:  {"setup": {"model":..., "responseModalities":["AUDIO"],
                     "outputAudioTranscription":{}, "inputAudioTranscription":{},
                     "systemInstruction":{...}, "tools":[...],
                     "realtimeInputConfig":{"automaticActivityDetection":{"disabled":True}}}}
  habla:  {"realtimeInput": {"activityStart": {}}}
  audio:  {"realtimeInput": {"audio": {"data":<b64 PCM>, "mimeType":"audio/pcm;rate=16000"}}}
  fin:    {"realtimeInput": {"activityEnd": {}}}
  texto:  {"realtimeInput": {"text": "..."}}
  tools:  {"toolResponse": {"functionResponses":[...]}}
  recibe: serverContent.modelTurn.parts[].inlineData.data  (audio 24 kHz)
          serverContent.outputTranscription.text           (lo que dice)
          serverContent.inputTranscription.text            (lo que oye)
          serverContent.interrupted                        (barge-in nativo)
          serverContent.turnComplete

Modulo NUEVO: no toca el camino de un turno ni el camino viejo (espeak/gemini/openai).
"""
import base64
import json
import os
import queue
import subprocess
import threading
import time

MODEL = "gemini-3.1-flash-live-preview"
URL = ("wss://generativelanguage.googleapis.com/ws/"
       "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")

MIC_RATE = 16000
SPK_RATE = 24000
CHUNK_MS = 100
CHUNK = MIC_RATE * 2 * CHUNK_MS // 1000        # 3200 bytes = 100 ms

# VAD local (energia). Medido en el portatil: silencio RMS ~270-580 sin hablar.
UMBRAL_HABLA = 500        # por encima: el usuario esta hablando
CHUNKS_SILENCIO_FIN = 8   # 800 ms de silencio -> fin de turno
CHUNKS_MIN_HABLA = 3      # 300 ms de habla minima para considerarlo voz


def _log(msg):
    try:
        with open("/tmp/aios-gemini-live.log", "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def _log_reset():
    try:
        open("/tmp/aios-gemini-live.log", "w").close()
    except Exception:
        pass


def _schema(p):
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
    decls = []
    for t in tools or []:
        fn = (t or {}).get("function") or {}
        if not fn.get("name"):
            continue
        d = {"name": fn["name"]}
        if fn.get("description"):
            d["description"] = fn["description"]
        if fn.get("parameters"):
            d["parameters"] = _schema(fn["parameters"])
        decls.append(d)
    return [{"functionDeclarations": decls}] if decls else []


def available():
    if not os.environ.get("GOOGLE_API_KEY"):
        return False, "no GOOGLE_API_KEY"
    try:
        import websockets  # noqa
    except ImportError:
        return False, "websockets not installed"
    return True, ""


def _rms(dato):
    """Energia del trozo PCM 16-bit, sin audioop (no existe en 3.13+)."""
    try:
        import array
        a = array.array("h")
        a.frombytes(dato[:len(dato) // 2 * 2])
        if not a:
            return 0
        return int((sum(x * x for x in a) / len(a)) ** 0.5)
    except Exception:
        return 0


class _Mic:
    """arecord en continuo -> cola de trozos PCM 16 kHz mono."""

    def __init__(self, q):
        self.q = q
        self.p = None
        self.parar = threading.Event()

    def start(self):
        try:
            self.p = subprocess.Popen(
                ["arecord", "-q", "-f", "S16_LE", "-r", str(MIC_RATE), "-c", "1", "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception as e:
            _log("micro no arranca: %s" % e)
            self.p = None
            return False
        threading.Thread(target=self._leer, daemon=True).start()
        return True

    def _leer(self):
        while not self.parar.is_set():
            try:
                dato = self.p.stdout.read(CHUNK)
            except Exception:
                break
            if not dato:
                break
            try:
                self.q.put_nowait(dato)
            except queue.Full:
                pass      # vamos por detras: descartar es mejor que acumular

    def stop(self):
        self.parar.set()
        if self.p:
            try:
                self.p.terminate()
                self.p.wait(timeout=3)
            except Exception:
                try:
                    self.p.kill()
                except Exception:
                    pass
            self.p = None


class _Teclado:
    """stdin por lineas -> cola de textos (el prompt sigue disponible)."""

    def __init__(self, q):
        self.q = q
        self.parar = threading.Event()

    def start(self):
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self):
        while not self.parar.is_set():
            try:
                linea = input()
            except (EOFError, KeyboardInterrupt):
                self.q.put(None)
                return
            except Exception:
                return
            if not self.parar.is_set():
                self.q.put(linea)

    def stop(self):
        self.parar.set()


def converse(system_prompt=None, tools=None, tool_runner=None,
             out_sink=None, audio_open=None, audio_feed=None, audio_close=None,
             cfg=None):
    """Bucle de conversacion natural con el micro. Bloquea hasta Ctrl+C / EOF.

    Devuelve (ok, motivo). Nunca lanza.
    """
    ok, why = available()
    if not ok:
        return False, why

    import asyncio
    import websockets

    mic_q = queue.Queue(maxsize=200)
    txt_q = queue.Queue()
    mic = _Mic(mic_q)
    tec = _Teclado(txt_q)
    est = {"turnos": 0, "audio": 0, "salir": False, "hablando": False,
           "n_habla": 0, "n_silencio": 0}

    async def main():
        key = os.environ.get("GOOGLE_API_KEY", "")
        setup = {
            "model": "models/" + MODEL,
            "generationConfig": {"responseModalities": ["AUDIO"]},
            "outputAudioTranscription": {},
            "inputAudioTranscription": {},
            # VAD MANUAL: la automatica no detecta el audio por trozos (medido).
            "realtimeInputConfig": {
                "automaticActivityDetection": {"disabled": True},
            },
        }
        if system_prompt:
            setup["systemInstruction"] = {"parts": [{"text": system_prompt[:30000]}]}
        gt = _geminify(tools)
        if gt:
            setup["tools"] = gt

        async with websockets.connect(URL + "?key=" + key,
                                      open_timeout=30, close_timeout=5,
                                      max_size=None) as ws:
            await ws.send(json.dumps({"setup": setup}))
            raw = await asyncio.wait_for(ws.recv(), timeout=40)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")
            if "setupComplete" not in raw:
                _log("setup inesperado: %s" % raw[:300])
                return
            _log("sesion iniciada (VAD local, umbral=%d)" % UMBRAL_HABLA)
            if out_sink:
                out_sink("\n(escuchando: habla cuando quieras; escribe para texto, "
                         "Ctrl+C para salir)\n")

            loop = asyncio.get_event_loop()

            async def enviar_micro():
                while not est["salir"]:
                    try:
                        trozo = await loop.run_in_executor(None, mic_q.get, True, 0.25)
                    except queue.Empty:
                        continue
                    except Exception:
                        break
                    if trozo is None:
                        break

                    # --- VAD local: decidir activityStart / activityEnd ---
                    nivel = _rms(trozo)
                    if nivel >= UMBRAL_HABLA:
                        est["n_habla"] += 1
                        est["n_silencio"] = 0
                        if not est["hablando"] and est["n_habla"] >= CHUNKS_MIN_HABLA:
                            est["hablando"] = True
                            await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))
                            _log("activityStart (hablas)")
                    else:
                        est["n_silencio"] += 1
                        if est["hablando"] and est["n_silencio"] >= CHUNKS_SILENCIO_FIN:
                            est["hablando"] = False
                            est["n_habla"] = 0
                            await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))
                            _log("activityEnd (callas)")

                    await ws.send(json.dumps({
                        "realtimeInput": {
                            "audio": {
                                "data": base64.b64encode(trozo).decode(),
                                "mimeType": "audio/pcm;rate=%d" % MIC_RATE,
                            }
                        }
                    }))

            async def enviar_texto():
                while not est["salir"]:
                    try:
                        linea = await loop.run_in_executor(None, txt_q.get, True, 0.25)
                    except queue.Empty:
                        continue
                    except Exception:
                        break
                    if linea is None:
                        break
                    linea = (linea or "").strip()
                    if not linea:
                        continue
                    if linea.lower() in ("salir", "exit", "quit", "/exit", "/salir"):
                        est["salir"] = True
                        return
                    if out_sink:
                        out_sink("\n> %s\n" % linea)
                    await ws.send(json.dumps({"realtimeInput": {"text": linea}}))

            async def recibir():
                while not est["salir"]:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=600)
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        return
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", "replace")
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if msg.get("toolCall"):
                        respuestas = []
                        for fc in (msg["toolCall"].get("functionCalls") or []):
                            nombre = fc.get("name", "")
                            args = fc.get("args") or {}
                            _log("tool: %s %s" % (nombre, str(args)[:140]))
                            try:
                                res = tool_runner(nombre, args) if tool_runner else "{}"
                            except Exception as e:
                                res = json.dumps({"error": str(e)[:200]})
                            respuestas.append({
                                "id": fc.get("id", ""),
                                "name": nombre,
                                "response": {"result": str(res)[:6000]},
                            })
                        await ws.send(json.dumps({
                            "toolResponse": {"functionResponses": respuestas}}))
                        continue

                    sc = msg.get("serverContent") or {}
                    if sc.get("interrupted"):
                        _log("barge-in: el usuario interrumpio")
                        if out_sink:
                            out_sink("\n[tú]\n")

                    for part in ((sc.get("modelTurn") or {}).get("parts") or []):
                        data = (part.get("inlineData") or {}).get("data")
                        if data:
                            trozo = base64.b64decode(data)
                            est["audio"] += len(trozo)
                            if audio_feed:
                                audio_feed(trozo)
                        if part.get("text") and out_sink:
                            out_sink(part["text"])

                    ot = (sc.get("outputTranscription") or {}).get("text")
                    if ot and out_sink:
                        out_sink(ot)

                    if sc.get("turnComplete"):
                        est["turnos"] += 1
                        if out_sink:
                            out_sink("\n")

            tareas = [asyncio.create_task(enviar_micro()),
                      asyncio.create_task(enviar_texto()),
                      asyncio.create_task(recibir())]
            try:
                while not est["salir"]:
                    await asyncio.sleep(0.2)
                    if all(t.done() for t in tareas):
                        break
            finally:
                for t in tareas:
                    t.cancel()

    if audio_open:
        audio_open()
    if not mic.start():
        _log("sin micro; solo texto")
    tec.start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log("Ctrl+C: fin de la conversacion")
    except Exception as e:
        _log("error: %s: %s" % (type(e).__name__, str(e)[:200]))
        return False, "%s: %s" % (type(e).__name__, str(e)[:120])
    finally:
        est["salir"] = True
        mic.stop()
        tec.stop()
        if audio_close:
            audio_close()

    return True, "turnos=%d audio=%.1fs" % (est["turnos"], est["audio"] / (SPK_RATE * 2))
