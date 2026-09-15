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

# Voz del Live. Sin esto el modelo ELIGE la voz y cambia (medido: cambiaba entre
# turnos). Debe ir DENTRO de generationConfig: al nivel del setup la API lo
# rechaza con "Unknown name speechConfig".
# Se puede cambiar con `voice.live_voice` en config.yaml.
# Voces disponibles (30): Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede,
# Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome,
# Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux,
# Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat
VOZ_POR_DEFECTO = "Kore"
IDIOMA_VOZ = "es-ES"       # espanol de Espana (acento castellano)
CHUNK_MS = 100
CHUNK = MIC_RATE * 2 * CHUNK_MS // 1000        # 3200 bytes = 100 ms

# VAD local (energia). El umbral NO puede ser una constante fija: medido en el
# portatil, el ruido de fondo tiene RMS ~180 y la voz del usuario ~550, asi que
# un umbral fijo de 500 dejaba la voz EN EL FILO y `activityStart` no se disparaba
# nunca (el Live oia silencio y no contestaba). El umbral se CALIBRA al arrancar
# con el ruido real de ESE micro.
CALIB_MS = 1500            # al arrancar se mide el ruido de fondo
CALENT_MS = 1000           # primeros ms de arecord: transitorio, se descarta
FACTOR_RUIDO = 2.2         # umbral = piso_ruido * FACTOR_RUIDO
UMBRAL_MIN = 120           # suelo, para micros muy silenciosos
UMBRAL_MAX = 600           # techo: un pico en la calibracion no puede dejarnos sordos
GANANCIA = 3.0             # ganancia digital antes de mandar el audio al Live
                           # (medido: la voz llegaba con pico 3.900/32.767 = 12%)
CHUNKS_SILENCIO_FIN = 8    # 800 ms de silencio -> fin de turno
COOLDOWN_MS = 300          # minimo tras hablar el Live antes de mirar el eco
ECO_LIBRE_TROZOS = 4       # trozos seguidos bajo el umbral para dar el eco por ido
ECO_MAX_MS = 4000          # tope: no dejar al usuario mudo si el ruido no baja
CHUNKS_MIN_HABLA = 3       # 300 ms de habla minima para considerarlo voz


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


def _amplifica(dato):
    """Amplifica el PCM 16-bit con saturacion (sin desbordar).

    Medido en el portatil: la voz llega con pico ~3.900 de 32.767 (12%), muy baja
    para que el Live la entienda bien. Se multiplica y se recorta al rango valido.
    """
    if GANANCIA == 1.0:
        return dato
    try:
        import array
        a = array.array("h")
        a.frombytes(dato[:len(dato) // 2 * 2])
        for i, v in enumerate(a):
            v = int(v * GANANCIA)
            if v > 32767:
                v = 32767
            elif v < -32768:
                v = -32768
            a[i] = v
        return a.tobytes()
    except Exception:
        return dato


class _Mic:
    """arecord en continuo -> cola de trozos PCM 16 kHz mono.

    Ademas CALIBRA el ruido de fondo: los primeros CALIB_MS trozos se miden y se
    fija el umbral del VAD a partir de ellos. Sin esto, un umbral fijo no vale
    para todos los micros (el ALC3227 del portatil da ruido ~180 y voz ~550).
    """

    def __init__(self, q):
        self.q = q
        self.p = None
        self.parar = threading.Event()
        self.piso_ruido = None       # RMS del ruido de fondo medido al arrancar
        self.umbral = None           # umbral resultante
        self.calibrado = threading.Event()
        self._calib = []             # niveles de la calibracion

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
        # el bucle de conversacion espera a tener umbral antes de enviar nada
        self.calibrado.wait(timeout=6)
        return True

    def _leer(self):
        n_calib = max(1, CALIB_MS // CHUNK_MS)
        # arecord entrega un transitorio en los primeros trozos (medido: el piso
        # salia 160 cuando el ruido real era 13-17, y el umbral quedaba al filo de
        # la voz). Se DESCARTA el calentamiento antes de calibrar.
        n_calent = max(1, CALENT_MS // CHUNK_MS)
        vistos = 0
        calent = 0
        while not self.parar.is_set():
            try:
                dato = self.p.stdout.read(CHUNK)
            except Exception:
                break
            if not dato:
                break
            if calent < n_calent:
                calent += 1          # calentamiento: se tira, no se mide
                continue
            if vistos < n_calib:
                # --- calibracion: medir el ruido de fondo de ESTE micro ---
                self._calib.append(_rms(dato))
                vistos += 1
                if vistos >= n_calib:
                    niveles = sorted(self._calib)
                    # percentil 25: si en la calibracion cae un golpe o un pico
                    # transitorio (paso: midio 135 cuando el ruido real era 14),
                    # la mediana se contamina y el umbral sale demasiado alto.
                    self.piso_ruido = niveles[len(niveles) // 4]
                    self.umbral = min(UMBRAL_MAX,
                                      max(UMBRAL_MIN, int(self.piso_ruido * FACTOR_RUIDO)))
                    _log("calibrado: piso_ruido=%d -> umbral=%d (ganancia=%.1f)"
                         % (self.piso_ruido, self.umbral, GANANCIA))
                    self.calibrado.set()
                continue
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
           "n_habla": 0, "n_silencio": 0,
           # anti-realimentacion: el Live no debe oirse a si mismo
           "live_hablando": False, "fin_voz": 0.0,
           # tras el turno del Live: no reanudar hasta que el eco se vaya
           "eco_esperando": False, "eco_trozos": 0, "eco_inicio": 0.0}

    async def main():
        key = os.environ.get("GOOGLE_API_KEY", "")
        # la voz: config.yaml manda; si no, el defecto
        voz = VOZ_POR_DEFECTO
        try:
            voz = ((cfg or {}).get("voice", {}) or {}).get("live_voice") or VOZ_POR_DEFECTO
        except Exception:
            pass
        _log("voz: %s" % voz)

        setup = {
            "model": "models/" + MODEL,
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voz}},
                    "languageCode": IDIOMA_VOZ,
                },
            },
            "outputAudioTranscription": {},
            "inputAudioTranscription": {},
            # VAD MANUAL: la automatica no detecta el audio por trozos (medido).
            "realtimeInputConfig": {
                "automaticActivityDetection": {"disabled": True},
            },
        }
        if system_prompt:
            # El Live respondia en INGLES aunque el prompt de AIOS esta en ingles:
            # languageCode fija la VOZ, no el idioma de la respuesta. Se anade una
            # instruccion explicita AL FINAL (no se sustituye nada del prompt).
            _apendice = ("\n\n[VOICE MODE] Speak ONLY in Spanish (es-ES, castellano "
                         "de Espana). Always answer out loud in Spanish, even if this "
                         "system prompt is written in English. Keep it short and natural.")
            setup["systemInstruction"] = {"parts": [{"text": (system_prompt + _apendice)[:30000]}]}
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
            _log("sesion iniciada (VAD local adaptativo, umbral=%s, ganancia=%.1f)"
                 % (mic.umbral, GANANCIA))
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

                    # --- ANTI-REALIMENTACION ---
                    # Si el Live esta hablando (o acaba de terminar), NO se manda
                    # su propia voz de vuelta como si fuera el usuario. Sin esto el
                    # Live se oye, se contesta y no para (medido: 7 turnos y 6
                    # barge-in a partir de un unico "Hola" del usuario).
                    ahora = time.time()
                    # Red de seguridad: si no llego el turnComplete, el micro no
                    # puede quedarse mudo para siempre.
                    if est["live_hablando"] and (ahora - est.get("inicio_voz", 0)) > 30:
                        _log("aviso: el Live lleva >30s sin turnComplete; se reanuda el micro")
                        est["live_hablando"] = False
                        est["fin_voz"] = ahora
                        est["eco_esperando"] = False

                    # --- ¿hay que ignorar el micro AHORA? ---
                    ignorar = False
                    if est["live_hablando"]:
                        ignorar = True
                    elif est["eco_esperando"]:
                        # el Live ya termino, pero el altavoz puede seguir sonando:
                        # se espera a que el nivel baje (el eco se va) o al tope.
                        if _rms(trozo) < (mic.umbral or UMBRAL_MIN):
                            est["eco_trozos"] += 1
                            if est["eco_trozos"] >= ECO_LIBRE_TROZOS:
                                est["eco_esperando"] = False
                                _log("eco ido: se reanuda el micro")
                        else:
                            est["eco_trozos"] = 0
                        if (ahora - est["eco_inicio"]) > (ECO_MAX_MS / 1000.0):
                            est["eco_esperando"] = False
                            _log("eco: tope de %d ms alcanzado; se reanuda el micro" % ECO_MAX_MS)
                        ignorar = est["eco_esperando"]
                    elif (ahora - est["fin_voz"]) < (COOLDOWN_MS / 1000.0):
                        ignorar = True

                    if ignorar:
                        if est["hablando"]:
                            est["hablando"] = False
                            est["n_habla"] = 0
                            await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))
                        await ws.send(json.dumps({
                            "realtimeInput": {"audio": {
                                "data": base64.b64encode(b"\x00" * len(trozo)).decode(),
                                "mimeType": "audio/pcm;rate=%d" % MIC_RATE}}}))
                        continue

                    # --- VAD local: decidir activityStart / activityEnd ---
                    # El umbral viene de la CALIBRACION del micro (ruido real de
                    # ESTE equipo). Si aun no hay umbral, se usa el minimo.
                    umbral = mic.umbral or UMBRAL_MIN
                    nivel = _rms(trozo)

                    # Diagnostico: el log debe decir el nivel SIEMPRE, no solo
                    # cuando dispara. Sin esto, "no me oye" es indistinguible de
                    # "el nivel no llega" (y se acaba adivinando).
                    est["nivel_max"] = max(est.get("nivel_max", 0), nivel)
                    est["n_trozos"] = est.get("n_trozos", 0) + 1
                    if est["n_trozos"] % 50 == 0:          # cada 5 s
                        _log("nivel max en 5s: %d (umbral %d, hablando=%s)"
                             % (est["nivel_max"], umbral, est["hablando"]))
                        est["nivel_max"] = 0

                    if nivel >= umbral:
                        est["n_habla"] += 1
                        est["n_silencio"] = 0
                        if not est["hablando"] and est["n_habla"] >= CHUNKS_MIN_HABLA:
                            est["hablando"] = True
                            await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))
                            _log("activityStart (hablas, nivel=%d umbral=%d)" % (nivel, umbral))
                    else:
                        est["n_silencio"] += 1
                        if est["hablando"] and est["n_silencio"] >= CHUNKS_SILENCIO_FIN:
                            est["hablando"] = False
                            est["n_habla"] = 0
                            await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))
                            _log("activityEnd (callas)")

                    # Ganancia digital: la voz del portatil llega muy baja (medido:
                    # pico 3.900/32.767 = 12%) y el Live entiende mal con tan poca
                    # amplitud. Se amplifica ANTES de enviar.
                    await ws.send(json.dumps({
                        "realtimeInput": {
                            "audio": {
                                "data": base64.b64encode(_amplifica(trozo)).decode(),
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
                        # al interrumpir, el Live deja de hablar: si no se limpia
                        # aqui, live_hablando se queda True y el micro no vuelve
                        est["live_hablando"] = False
                        est["fin_voz"] = time.time()
                        est["eco_esperando"] = True
                        est["eco_trozos"] = 0
                        est["eco_inicio"] = time.time()
                        if out_sink:
                            out_sink("\n[tú]\n")

                    for part in ((sc.get("modelTurn") or {}).get("parts") or []):
                        data = (part.get("inlineData") or {}).get("data")
                        if data:
                            trozo = base64.b64decode(data)
                            est["audio"] += len(trozo)
                            est["live_hablando"] = True      # anti-realimentacion
                            est["inicio_voz"] = time.time()
                            if audio_feed:
                                audio_feed(trozo)
                        if part.get("text") and out_sink:
                            out_sink(part["text"])

                    # LO QUE TE OYE: el setup pide `inputAudioTranscription`, asi
                    # que el servidor manda la transcripcion de tu voz. Antes NO se
                    # leia (se tiraba), y por eso no habia forma de ver que habia
                    # entendido el Live: se mostraba solo lo que el decia.
                    it = (sc.get("inputTranscription") or {}).get("text")
                    if it:
                        est["oyo"] = est.get("oyo", "") + it
                        _log("oyo: %s" % it.replace("\n", " ")[:200])
                        if out_sink:
                            out_sink("\r\nyou: %s\n" % it)

                    ot = (sc.get("outputTranscription") or {}).get("text")
                    if ot:
                        est["dijo"] = est.get("dijo", "") + ot
                        if out_sink:
                            out_sink(ot)

                    if sc.get("turnComplete"):
                        est["turnos"] += 1
                        # el Live deja de hablar: se espera a que el eco se vaya
                        est["live_hablando"] = False
                        est["fin_voz"] = time.time()
                        est["eco_esperando"] = True
                        est["eco_trozos"] = 0
                        est["eco_inicio"] = time.time()
                        _log("turno %d: oyo=%r dijo=%r"
                             % (est["turnos"], est.get("oyo", "")[-160:],
                                est.get("dijo", "")[-160:]))
                        est["oyo"] = ""
                        est["dijo"] = ""
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
    _log_reset()          # el log es de ESTA sesion (no arrastra el de ayer)
    _log("--- inicio de conversacion (ganancia=%.1f) ---" % GANANCIA)
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
