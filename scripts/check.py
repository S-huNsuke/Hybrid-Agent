#!/usr/bin/env python3
"""Local Harness verification script covering the M0 prerequisites."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_BIN = ROOT / ".venv" / "bin"
PROJECT_PYTHON = VENV_BIN / "python"

REQUIRED_PATHS = [
    ("CLAUDE.md", Path("CLAUDE.md")),
    ("claude-progress.txt", Path("claude-progress.txt")),
    ("KNOWN_FAILURES.md", Path("KNOWN_FAILURES.md")),
    ("docs/architecture.md", Path("docs/architecture.md")),
    ("docs/conventions.md", Path("docs/conventions.md")),
    ("scripts/check.py", Path("scripts/check.py")),
    ("tests/test_architecture.py", Path("tests/test_architecture.py")),
    (".github/workflows/ci.yml", Path(".github/workflows/ci.yml")),
    ("frontend/package.json", Path("frontend/package.json")),
]

TOOL_CHECKS = [
    (
        "ruff",
        ["ruff", "check", "src/", "--output-format=concise"],
        "install it into the project environment or PATH, then rerun this check",
    ),
    (
        "mypy",
        ["mypy", "src/hybrid_agent", "--ignore-missing-imports"],
        "install it into the project environment or PATH, then rerun this check",
    ),
]


def check_required_files() -> list[str]:
    missing: list[str] = []
    for label, rel_path in REQUIRED_PATHS:
        if not (ROOT / rel_path).exists():
            missing.append(f"missing {label} ({rel_path})")
    return missing


def resolve_tool(name: str) -> str | None:
    project_tool = VENV_BIN / name
    if project_tool.exists():
        return str(project_tool)
    return shutil.which(name)


def run_tool(name: str, command: list[str], install_hint: str) -> str | None:
    executable = resolve_tool(command[0])
    if executable is None:
        return f"{name} not installed ({install_hint})"

    final_command = [executable, *command[1:]]
    try:
        subprocess.run(final_command, cwd=ROOT, check=True)
        return None
    except subprocess.CalledProcessError as exc:
        return f"{name} failed (exit {exc.returncode})"


def run_pytest() -> str | None:
    if not PROJECT_PYTHON.exists():
        return "project virtualenv missing (run `uv sync --extra dev` first)"

    import_check = [str(PROJECT_PYTHON), "-c", "import pytest"]
    try:
        subprocess.run(
            import_check,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return "pytest not installed in the project environment (run `uv sync --extra dev` first)"

    env = {"PYTHONPATH": str(ROOT / "src"), **os.environ}
    cmd = [str(PROJECT_PYTHON), "-m", "pytest", "tests/", "--tb=short", "-q"]
    try:
        subprocess.run(cmd, cwd=ROOT, env=env, check=True)
        return None
    except subprocess.CalledProcessError as exc:
        return f"pytest failed (exit {exc.returncode})"


def main() -> None:
    failures: list[str] = []
    failures.extend(check_required_files())

    for name, command, hint in TOOL_CHECKS:
        message = run_tool(name, command, hint)
        if message:
            failures.append(message)

    test_message = run_pytest()
    if test_message:
        failures.append(test_message)

    if failures:
        print("Harness check failed; see issues below:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)


if __name__ == "__main__":
    main()
