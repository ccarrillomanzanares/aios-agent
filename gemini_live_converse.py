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
VOZ_POR_DEFECTO = "Sulafat"
IDIOMA_VOZ = "es-ES"       # espanol de Espana (acento castellano)
CHUNK_MS = 100
CHUNK = MIC_RATE * 2 * CHUNK_MS // 1000        # 3200 bytes = 100 ms

# VAD local (energia), SIN calibracion. Carlos: "no hagas calibracion, lo complica".
#
# La calibracion dio un resultado distinto cada vez (midio 135 con ruido real 14;
# 160 por el transitorio de arecord; y 814 = SU VOZ al arrancar, que dejaba el
# umbral en el techo y sordo toda la sesion). Umbral fijo y medido.
#
# Numeros medidos en este portatil (Capture 45%, voz real de Carlos):
#     VOZ:   p50 = 330, p90 = 830, max = 1784 (picos de 6760-9992 en uso real)
#     RUIDO: p50 = 14-20, p90 = 45
UMBRAL_HABLA = 400         # holgadamente por encima del ruido y dentro de la voz
GANANCIA = 3.0             # ganancia digital antes de mandar el audio al Live
                           # (medido: la voz llegaba con pico 3.900/32.767 = 12%)
# 1500 ms de silencio para cerrar el turno. Con 800 ms la frase se cortaba por la
# mitad (al hablar se hacen pausas normales: pensar, respirar), el Live recibia
# trozos sueltos y NO respondia. Medido con umbral 250: 8 activityStart, 0 turnos.
CHUNKS_SILENCIO_FIN = 15
COOLDOWN_MS = 300          # margen tras terminar la reproduccion
MARGEN_REPRO_MS = 500      # margen por latencia de aplay
ECO_MAX_MS = 30000         # tope de seguridad: nunca mudo mas de 30 s
# Reconexion: la sesion del Live se cae sola (medido: el proceso quedaba vivo pero
# sin conexion ni micro, mudo durante horas). Hay que detectarlo y reconectar.
SIN_TRAFICO_MS = 60000     # 60 s sin NINGUN mensaje del servidor = sesion muerta
RECONEX_INTENTOS = 3       # intentos antes de rendirse y volver al prompt
RECONEX_ESPERA_MS = 1500   # espera entre intentos (crece con cada fallo)
CHUNKS_MIN_HABLA = 2       # 200 ms: no perder frases cortas


def _limpia_procesos_audio():
    """Mata los arecord/aplay del agente al salir.

    Medido: si el agente muere sin hacerlo, sus hijos quedan HUERFANOS con el audio
    abierto; como el micro tiene una sola entrada, NINGUNA app puede sonar y el
    equipo parece colgado. Y no mueren con TERM: hace falta KILL.
    """
    import subprocess as _sp
    for nombre in ("arecord", "aplay"):
        try:
            _sp.run(["pkill", "-9", "-x", nombre], capture_output=True, timeout=5)
        except Exception:
            pass


def _log(msg):
    try:
        with open("/tmp/aios-gemini-live.log", "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def _instala_limpieza_por_senal():
    """Libera el audio si matan el agente desde fuera (SIGTERM/SIGINT/SIGHUP)."""
    import atexit
    import signal

    def _salida(*_a):
        _limpia_procesos_audio()
        raise SystemExit(0)

    atexit.register(_limpia_procesos_audio)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, _salida)
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
    """arecord en continuo -> cola de trozos PCM 16 kHz mono."""

    def __init__(self, q):
        self.q = q
        self.p = None
        self.parar = threading.Event()
        self.umbral = UMBRAL_HABLA   # fijo (sin calibracion; ver arriba)

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

    _instala_limpieza_por_senal()
    mic_q = queue.Queue(maxsize=200)
    txt_q = queue.Queue()
    mic = _Mic(mic_q)
    tec = _Teclado(txt_q)
    est = {"turnos": 0, "audio": 0, "salir": False, "hablando": False,
           "n_habla": 0, "n_silencio": 0, "caida": None,
           # anti-realimentacion: el Live no debe oirse a si mismo
           "live_hablando": False, "fin_voz": 0.0,
           # anti-eco por BYTES: el audio suena a 24 kHz, asi que la duracion
           # es bytes/(24000*2) s. Con eso se sabe cuando TERMINA de sonar.
           "audio_total": 0, "audio_t0": 0.0, "repro_hasta": 0.0}

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
            _log("sesion iniciada (VAD fijo, umbral=%d, ganancia=%.1f)"
                 % (UMBRAL_HABLA, GANANCIA))
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

                    # --- ANTI-ECO (por BYTES, no por silencios) ---
                    # El Live se oia a si mismo: con la v2 (esperar silencio) hacia
                    # PAUSAS entre frases, el micro se reanudaba y pillaba la frase
                    # siguiente: "you: Son las 9:20 de la manana" = su PROPIA voz.
                    # La API no trae cancelacion de eco, asi que se calcula CUANDO
                    # TERMINA de sonar: el audio va a 24 kHz -> bytes/(24000*2) s.
                    ahora = time.time()
                    if est["live_hablando"] and (ahora - est.get("inicio_voz", 0)) > (ECO_MAX_MS / 1000.0):
                        _log("aviso: el Live lleva >%ds sin terminar; se reanuda el micro" % (ECO_MAX_MS // 1000))
                        est["live_hablando"] = False
                        est["repro_hasta"] = ahora

                    ignorar = (est["live_hablando"]
                               or ahora < (est["repro_hasta"] + COOLDOWN_MS / 1000.0))

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
                    umbral = UMBRAL_HABLA
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
                            # turno NUEVO del usuario: la medida de audio anterior ya no vale
                            est["audio_total"] = 0
                            est["audio_t0"] = 0.0
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
                        raw = await asyncio.wait_for(ws.recv(), timeout=SIN_TRAFICO_MS / 1000.0)
                    except asyncio.TimeoutError:
                        # mucho tiempo sin nada del servidor: puede ser normal si
                        # nadie habla, asi que solo se registra (no se corta).
                        _log("aviso: %ds sin trafico del servidor" % (SIN_TRAFICO_MS // 1000))
                        continue
                    except Exception as e:
                        # AQUI se detecta la caida real de la sesion
                        est["caida"] = "%s: %s" % (type(e).__name__, str(e)[:120])
                        _log("SESION CAIDA: %s" % est["caida"])
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
                        # al interrumpir, se corta el audio: fin de reproduccion ya
                        est["repro_hasta"] = time.time()
                        est["audio_total"] = 0
                        est["audio_t0"] = 0.0
                        if out_sink:
                            out_sink("\n[tú]\n")

                    for part in ((sc.get("modelTurn") or {}).get("parts") or []):
                        data = (part.get("inlineData") or {}).get("data")
                        if data:
                            trozo = base64.b64decode(data)
                            est["audio"] += len(trozo)
                            # anti-eco: acumular bytes y estimar el fin de la
                            # reproduccion (24 kHz, 16-bit mono)
                            est["audio_total"] = est.get("audio_total", 0) + len(trozo)
                            if not est.get("audio_t0"):
                                est["audio_t0"] = time.time()
                            est["repro_hasta"] = (est["audio_t0"]
                                                  + est["audio_total"] / float(SPK_RATE * 2))
                            if not est["live_hablando"]:
                                est["live_hablando"] = True
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
                        # el turno acaba, pero el altavoz sigue sonando: NO se
                        # reanuda el micro hasta que la reproduccion termina
                        est["live_hablando"] = False
                        est["fin_voz"] = ahora
                        est["repro_hasta"] = est.get("repro_hasta", 0) + MARGEN_REPRO_MS / 1000.0
                        _log("turno %d: micro en silencio hasta %.2fs (reproduccion)"
                             % (est["turnos"], est.get("repro_hasta", 0) - time.time()))
                        est["audio_total"] = 0
                        est["audio_t0"] = 0.0
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
                    # si la recepcion murio (sesion caida), se sale para reconectar
                    if est["caida"]:
                        break
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
    # Reconexion: si la sesion del Live se cae, se vuelve a conectar solo. Medido:
    # sin esto el proceso quedaba VIVO pero mudo (sin conexion ni micro) durante
    # HORAS, y el usuario le hablaba a un proceso muerto.
    try:
        for intento in range(1, RECONEX_INTENTOS + 1):
            est["caida"] = None
            try:
                asyncio.run(main())
            except KeyboardInterrupt:
                _log("Ctrl+C: fin de la conversacion")
                break
            except Exception as e:
                est["caida"] = "%s: %s" % (type(e).__name__, str(e)[:120])
                _log("error: %s" % est["caida"])

            if est["salir"] or not est["caida"]:
                break

            # se avisa al usuario (pantalla) y se reintenta
            if out_sink:
                out_sink("\n\n[conexion con Gemini cortada: %s]\n" % est["caida"])
                out_sink("[reconectando... intento %d de %d]\n" % (intento, RECONEX_INTENTOS))
            _log("reconectando (intento %d de %d)" % (intento, RECONEX_INTENTOS))
            time.sleep(RECONEX_ESPERA_MS * intento / 1000.0)
            est["hablando"] = False
            est["n_habla"] = 0
            est["n_silencio"] = 0
    finally:
        est["salir"] = True
        mic.stop()
        tec.stop()
        if audio_close:
            audio_close()
        # liberar SIEMPRE el audio (si no, quedan huerfanos y bloquean el sonido
        # del equipo entero: el micro tiene una sola entrada)
        _limpia_procesos_audio()

    return True, "turnos=%d audio=%.1fs" % (est["turnos"], est["audio"] / (SPK_RATE * 2))
