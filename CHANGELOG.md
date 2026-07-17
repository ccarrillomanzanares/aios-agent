# CHANGELOG.md

Todos los cambios notables de este proyecto se documentarán aquí.

## [Unreleased]

### Añadido
- `setup.sh`: instalador automático que verifica CPU, compila llama.cpp, crea venv, instala dependencias Python, descarga el modelo GGUF por defecto y reconstruye el índice RAG.
- `requirements.txt`: dependencias Python del proyecto.
- CHANGELOG.md: registro de cambios.

### Cambiado
- `README.md`: eliminadas referencias específicas al VPS y convertido a instrucciones genéricas con `./setup.sh`.
- `scripts/start_llm.sh`: paths absolutos reemplazados por paths relativos al directorio del proyecto.
- `rag/config.yaml`: `db_path` ahora es relativo (`./rag/chroma_db`).

### Arreglado
- Corrección de nombres en comandos anteriores: el orquestador detecta patrones como `no X, Y` y reemplaza la palabra en el comando manteniendo la acción.
- Executor con detección de inactividad: comandos como `apt install` que emiten progreso no mueren por timeout absoluto.

## [Initial] - 2026-07-17

### Añadido
- MVP de orquestador SRE con RAG local, LLM local y executor seguro.
- Modos del orquestador: EXPLAIN, COMMAND, PLAN, ASK, DONE.
- Dataset de 96 documentos SRE técnicos.
- Evaluación automática con `scripts/evaluate.py`.
- Documentación: README.md, STATUS.md, SECURITY.md, DECISIONS.md.
