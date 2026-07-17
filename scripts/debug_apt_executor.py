import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")
from executor import run_command

res = run_command("sudo apt install -y lynx", auto_approve_readonly=False, approved=True)
print("=== RESULTADO ===")
print("success:", res["success"])
print("returncode:", res["returncode"])
print("=== STDOUT COMPLETO ===")
print(res["stdout"])
print("=== STDERR COMPLETO ===")
print(res["stderr"])
