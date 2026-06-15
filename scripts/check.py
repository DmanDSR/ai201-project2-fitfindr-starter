"""
scripts/check.py — automated compliance & security gate for FitFindr.

Runs three checks on a single Python file:
  1. py_compile  — syntax must be valid
  2. ruff check  — lint / style compliance  (maps to BUILD_LOG N1)
  3. bandit -ll  — security, medium+ severity  (maps to BUILD_LOG N2)

Usage:
  - CLI:  python scripts/check.py path/to/file.py
  - Hook: invoked by Claude Code PostToolUse; the edited file path is read
          from the JSON payload on stdin (tool_input.file_path).

Exit codes:
  0  — clean (or target is not a project .py file → nothing to do)
  2  — findings reported on stderr (PostToolUse surfaces these back to Claude
       without reverting the edit, so issues get fixed immediately).
"""

import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable

# bandit: B101 = assert_used. Tests legitimately use asserts, so skip it.
BANDIT_SKIPS = "B101"


def _target_from_argv_or_stdin() -> str | None:
    """Resolve the file to check from argv[1], else from a PostToolUse JSON
    payload on stdin (tool_input.file_path / tool_response.filePath)."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    if sys.stdin.isatty():
        return None
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input", {}) or {}
    return (
        tool_input.get("file_path")
        or tool_input.get("filePath")
        or (payload.get("tool_response", {}) or {}).get("filePath")
    )


def _is_checkable(path: str) -> bool:
    """Only check real .py files inside the project, never the virtualenv."""
    if not path or not path.endswith(".py"):
        return False
    abspath = os.path.abspath(path)
    if not os.path.isfile(abspath):
        return False
    if not abspath.startswith(PROJECT_ROOT):
        return False
    parts = abspath.replace("\\", "/").split("/")
    return ".venv" not in parts


def _run(cmd: list[str]) -> tuple[int, str]:
    """Run a subprocess, return (returncode, combined output)."""
    proc = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def check_file(path: str) -> list[str]:
    """Run all three checks; return a list of human-readable problem reports."""
    problems: list[str] = []
    rel = os.path.relpath(os.path.abspath(path), PROJECT_ROOT)

    code, out = _run([PYTHON, "-m", "py_compile", path])
    if code != 0:
        problems.append(f"[syntax] {rel}:\n{out}")

    code, out = _run([PYTHON, "-m", "ruff", "check", path])
    if code != 0 and out:
        problems.append(f"[ruff/compliance] {rel}:\n{out}")

    code, out = _run(
        [PYTHON, "-m", "bandit", "-ll", "--skip", BANDIT_SKIPS, "-q", path]
    )
    if code != 0 and out:
        problems.append(f"[bandit/security] {rel}:\n{out}")

    return problems


def main() -> int:
    target = _target_from_argv_or_stdin()
    if not target or not _is_checkable(target):
        return 0

    problems = check_file(target)
    if not problems:
        print(f"[OK] checks passed: {os.path.basename(target)}")
        return 0

    sys.stderr.write(
        "[!] FitFindr automated checks found issues (fix before moving on):\n\n"
        + "\n\n".join(problems)
        + "\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
