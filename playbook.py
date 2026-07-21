"""Playbook mode for the SRE agent: read YAML, execute steps sequentially."""
import json
from pathlib import Path

import yaml



def run_playbook(path: str) -> str:
    """Read a YAML playbook and execute its steps sequentially.

    Returns a JSON string with a summary:
    {
        "playbook": str,
        "description": str,
        "steps_total": int,
        "steps_ok": int,
        "steps_fail": int,
        "results": [
            {
                "step": int,
                "name": str,
                "command": str,
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "ok": bool,
                "error": str | None
            }
        ]
    }
    """
    try:
        p = Path(path).resolve()
        if not p.exists():
            return json.dumps({"error": f"Playbook not found: {path}"}, ensure_ascii=False)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return json.dumps({"error": f"Invalid YAML: {e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    playbook_name = data.get("name", p.name)
    description = data.get("description", "")
    steps = data.get("steps", []) or []

    results = []
    steps_ok = 0
    steps_fail = 0
    failed = False

    for idx, step in enumerate(steps, start=1):
        if failed:
            results.append({
                "step": idx,
                "name": step.get("name", f"step-{idx}"),
                "command": step.get("command", ""),
                "exit_code": None,
                "stdout": "",
                "stderr": "Skipped: previous step failed",
                "ok": False,
                "error": "Skipped",
            })
            steps_fail += 1
            continue

        name = step.get("name", f"step-{idx}")
        command = step.get("command", "")
        timeout = step.get("timeout", 30)
        retry = step.get("retry", True)

        try:
            from tools import run_command
            output = json.loads(run_command(command, timeout=timeout, retry=retry))
        except Exception as e:
            output = {"stdout": "", "stderr": str(e), "exit_code": -1, "elapsed": 0}

        ok = output.get("exit_code") == 0
        if not ok:
            failed = True
            steps_fail += 1
        else:
            steps_ok += 1

        results.append({
            "step": idx,
            "name": name,
            "command": command,
            "exit_code": output.get("exit_code"),
            "stdout": output.get("stdout", ""),
            "stderr": output.get("stderr", ""),
            "ok": ok,
            "error": output.get("stderr", "") if not ok else None,
        })

    summary = {
        "playbook": playbook_name,
        "description": description,
        "steps_total": len(steps),
        "steps_ok": steps_ok,
        "steps_fail": steps_fail,
        "results": results,
    }
    return json.dumps(summary, ensure_ascii=False)
