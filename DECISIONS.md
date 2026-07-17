# Decisiones de diseño de SRE-Copilot

## 1. Plataforma

**Decisión:** VPS Linux (`31.220.80.78`).
**Razón:** El hardware local no tiene GPU y el objetivo es un asistente accesible vía SSH.

## 2. Backend LLM

**Decisión:** `llama.cpp` directo, no Ollama.
**Razón:** Mayor control sobre threads, contexto y quant. Evita capas intermedias.

## 3. Modelo

**Inicialmente propuesto:** Qwen3-8B Q5_K_M.
**Problema:** El repo descargado (`bartowski/Qwen_Qwen3-8B-GGUF`) era la versión base, no Instruct. Generaba razonamiento interno constante y no respondía adecuadamente.
**Decisión final:** `Meta-Llama-3.1-8B-Instruct-GGUF` Q5_K_M.
**Razón:** Provenido, template sencillo, buen rendimiento en CPU (~9-15 tok/s), multilingüe suficiente.

## 4. Embeddings

**Decisión:** `intfloat/multilingual-e5-large`.
**Razón:** Multilingüe (español/inglés técnico), buena calidad, 1024 dims.
**Alternativa descartada:** `nomic-embed-text-v1.5` (más rápido pero peor en multilingüe).

## 5. Vector DB

**Decisión:** ChromaDB local.
**Razón:** Ligero, fácil de embeber en Python, no requiere servidor externo.

## 6. Interfaz

**Decisión:** CLI interactivo por SSH.
**Razón:** Mínima superficie de ataque, rápida de iterar, alineada con el perfil SRE del usuario.

## 7. Seguridad del executor

**Decisión:** Whitelist de solo lectura + aprobación para el resto.
**Razón:** Balance entre utilidad y seguridad. Evita ejecuciones accidentales destructivas.

## 8. Dataset

**Decisión:** Documentación pública curada, sin memorias de Hermes.
**Razón:** El usuario pidió explícitamente no incluir memorias del perfil para evitar filtración de datos personales o credenciales.

## 9. Formato de LLM

**Decisión:** Usar `/v1/completions` con template manual de Llama-3.1.
**Razón:** La build b5200 de `llama.cpp` no aplica correctamente el chat template vía `/v1/chat.completions`, lo que provocaba razonamiento interno. El formato manual da respuestas directas.

## 10. `TMPDIR`

**Decisión:** Apuntar a `/home/ccmai/sre-copilot/tmp`.
**Razón:** El `/tmp` del VPS es tmpfs de 32 GB y se llena fácilmente con descargas grandes.

## 11. Servicio systemd

**Decisión:** Servicio de usuario `sre-llm.service` para el LLM; orquestador interactivo manual.
**Razón:** El LLM debe estar siempre disponible. El orquestador requiere interacción humana, así que no se automatiza como servicio.

## Lecciones aprendidas

- Verificar siempre si el GGUF descargado es base o Instruct antes de usarlo.
- Limpiar procesos `llama-server` huérfanos; pueden causar confusión en el puerto 8080.
- El prompt engineering es crítico: hay que indicar explícitamente cómo crear scripts y evitar redirecciones incorrectas.
