"""Tools for the SRE agent — native function calling."""
import json
import sys
import re
import signal
import subprocess
import time
from pathlib import Path

import requests
import yaml
from playbook import run_playbook
from process import process_start, process_send, process_close, process_list


def _is_blocked_command(command: str) -> bool:
    """Return True if command matches an unconditionally blocked dangerous pattern."""
    lower = command.lower()
    # rm -rf / or rm -rf /* (root destruction only)
    if re.search(r'\brm\s+-rf\s+/\s*$', lower) or re.search(r'\brm\s+-rf\s+/*\b', lower):
        return True
    if re.search(r'\bdd\s+if=\S+\s+of=/dev/\S+', lower):
        return True
    if re.search(r'\bmkfs\.\w+\s+\S+', lower):
        return True
    if re.search(r'\bfdisk\b', lower):
        return True
    if re.search(r'\bchmod\b.*(?:-r\s+)?000\b', lower):
        return True
    return False


def _is_destructive_command(command: str) -> bool:
    """Return True if command requires human confirmation before execution."""
    lower = command.lower()
    if re.search(r'\brm\b', lower):
        return True
    if re.search(r'\bsudo\s+rm\b', lower):
        return True
    if re.search(r'\b>\s*/dev/sd[a-z]', lower):
        return True
    if re.search(r'\bformat\b', lower):
        return True
    if re.search(r'\bdd\s+if=\S+', lower):
        return True
    return False


def _confirm_destructive(command: str, timeout: int = 10) -> bool:
    """Ask user for confirmation before running a destructive command."""
    sys.stderr.write(f"\u26a0\ufe0f Destructive command detected: {command}. Continue? (y/N): ")
    sys.stderr.flush()
    try:
        def _timeout_handler(signum, frame):
            raise TimeoutError
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        try:
            answer = sys.stdin.readline().strip()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        return answer in ("y", "Y")
    except TimeoutError:
        sys.stderr.write("Confirmation timeout\n")
        return False
    except Exception:
        return False
