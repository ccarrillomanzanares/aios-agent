import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")
from executor import run_command

print("=== TEST 1: Proceso con progreso durante 90s (debe completarse) ===")
res = run_command("bash -c 'for i in {1..30}; do echo \"progreso $$i\"; sleep 3; done; echo DONE'",
                  auto_approve_readonly=False, approved=True)
print("success:", res["success"])
print("returncode:", res["returncode"])
print("stdout tail:", "\n".join(res["stdout"].strip().splitlines()[-3:]))
print("stderr:", res["stderr"][:200])

print("\n=== TEST 2: Proceso que se cuelga 70s tras primer mensaje (debe morir por inactividad) ===")
res = run_command("bash -c 'echo inicio; sleep 70; echo fin'",
                  auto_approve_readonly=False, approved=True)
print("success:", res["success"])
print("returncode:", res["returncode"])
print("stdout:", res["stdout"].strip())
print("stderr:", res["stderr"].strip())

print("\n=== TEST 3: Comando rápido (debe funcionar) ===")
res = run_command("echo hola", auto_approve_readonly=False, approved=True)
print("success:", res["success"])
print("stdout:", res["stdout"].strip())
