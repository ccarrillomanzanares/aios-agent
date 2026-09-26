"""Interactive process management for the SRE agent.
Uses PTY for proper interactive terminal support (input(), password prompts, etc.)."""
import json
import os
import pty
import select
import subprocess
import time
import signal


class ProcessManager:
    def __init__(self):
        self._processes = {}

    def _read_all(self, fd, timeout=0.5):
        """Read available data from a PTY fd with timeout."""
        output = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    output += data.decode("utf-8", errors="replace")
                except OSError:
                    break
            else:
                break
        return output

    def start(self, command: str, timeout: int = 30) -> str:
        """Start a process in a PTY and return its ID plus initial output.

        MISMO guardian que run_command, y esto es un arreglo, no un adorno.
        La auditoria del 26 Sep 2026 lo midio: este fichero no consultaba el
        filtro en ninguna linea, asi que el mismo comando que run_command
        BLOQUEABA se ejecutaba aqui sin bloqueo y sin preguntar.

            _is_blocked_command("rm -rf <dir>")  -> True
            run_command("rm -rf <dir>")          -> "Command blocked"  (dir intacto)
            process_start("rm -rf <dir>")        -> exit_code 0       (dir BORRADO)

        No es un ataque: el prompt de produccion ordena usar process_start para
        scripts interactivos, asi que un modelo que sigue sus instrucciones cae
        aqui sin proponerselo. Si la capa no se puede importar, se falla CERRADO.
        """
        try:
            from tools import verificar_comando
        except Exception as e:
            return json.dumps({
                "error": f"Security layer unavailable, refusing to start: {e}",
                "exit_code": -1, "stdout": "", "stderr": "Fail closed",
            }, ensure_ascii=False)

        veredicto, motivo = verificar_comando(command)
        if veredicto == "bloquea":
            return json.dumps({
                "error": f"Command blocked: dangerous operation ({motivo})",
                "exit_code": -1, "stdout": "",
                "stderr": "Blocked for security reasons",
            }, ensure_ascii=False)
        if veredicto == "confirma":
            from tools import _confirm_destructive
            if not _confirm_destructive(command):
                return json.dumps({
                    "error": "Command cancelled by user", "exit_code": -1,
                    "stdout": "", "stderr": "Cancelled",
                }, ensure_ascii=False)

        proc_id = f"proc_{int(time.time() * 1000)}"
        try:
            master_fd, slave_fd = pty.openpty()
            proc = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=os.setsid,
            )
            os.close(slave_fd)

            initial = self._read_all(master_fd, timeout=min(timeout, 3))

            self._processes[proc_id] = {
                "master_fd": master_fd,
                "proc": proc,
                "command": command,
                "started": time.time(),
            }

            return json.dumps({
                "id": proc_id,
                "command": command,
                "stdout": initial[:2000],
                "running": proc.poll() is None,
                "exit_code": proc.poll(),
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": f"Failed to start process: {e}"}, ensure_ascii=False)

    def send(self, proc_id: str, text: str, timeout: int = 30) -> str:
        """Send input to a running process and read its response."""
        if proc_id not in self._processes:
            return json.dumps({"error": f"Process {proc_id} not found"}, ensure_ascii=False)

        proc_info = self._processes[proc_id]
        master_fd = proc_info["master_fd"]
        proc = proc_info["proc"]

        if proc.poll() is not None:
            return json.dumps({"error": f"Process exited with code {proc.poll()}"}, ensure_ascii=False)

        try:
            os.write(master_fd, (text + "\n").encode())
            output = self._read_all(master_fd, timeout=timeout)
            still_running = proc.poll() is None
            return json.dumps({
                "id": proc_id,
                "stdout": output[:2000],
                "running": still_running,
                "exit_code": proc.poll(),
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def close(self, proc_id: str) -> str:
        """Kill a process and clean up."""
        if proc_id not in self._processes:
            return json.dumps({"error": f"Process {proc_id} not found"}, ensure_ascii=False)

        proc_info = self._processes[proc_id]
        master_fd = proc_info["master_fd"]
        proc = proc_info["proc"]

        try:
            os.close(master_fd)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except Exception:
            pass

        del self._processes[proc_id]
        return json.dumps({"ok": True, "command": proc_info["command"]}, ensure_ascii=False)

    def list_processes(self) -> str:
        procs = []
        for pid, info in self._processes.items():
            proc = info["proc"]
            procs.append({
                "id": pid,
                "command": info["command"],
                "running": proc.poll() is None,
                "uptime": round(time.time() - info["started"], 1),
            })
        return json.dumps({"count": len(procs), "processes": procs}, ensure_ascii=False)


_manager = ProcessManager()


def process_start(command: str, timeout: int = 30) -> str:
    return _manager.start(command, timeout)


def process_close(proc_id: str) -> str:
    return _manager.close(proc_id)


def process_list() -> str:
    return _manager.list_processes()
