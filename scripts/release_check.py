#!/usr/bin/env python3
"""Release-readiness checks for Hybrid-Agent."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
E2E_MODES = {"required", "auto", "skip"}
PROJECT_PYTHON = ROOT / ".venv" / "bin" / "python"


def env_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def require_file(path: Path, label: str, failures: list[str]) -> None:
    if not path.exists():
        failures.append(f"missing {label}: {path.relative_to(ROOT)}")


def output_is_env_limited(output: str) -> bool:
    lowered = output.lower()
    markers = [
        "failed to launch browser",
        "executable doesn't exist",
        "browser has been closed",
        "sandbox",
        "permission denied",
        "operation not permitted",
        "no such file or directory",
        "playwright install",
        "missing dependencies",
        "/var/run/docker.sock",
        "cannot connect to the docker daemon",
        "already used, make sure that nothing is running on the port",
    ]
    return any(marker in lowered for marker in markers)


def resolve_python() -> str | None:
    if PROJECT_PYTHON.exists():
        return str(PROJECT_PYTHON)
    return shutil.which("python3") or shutil.which("python")


def parse_e2e_mode() -> str:
    mode = os.environ.get("RELEASE_E2E_MODE", "required").strip().lower()
    if mode not in E2E_MODES:
        raise ValueError(f"invalid RELEASE_E2E_MODE={mode!r}, expected one of: {', '.join(sorted(E2E_MODES))}")
    return mode


def run_e2e_smoke(
    *,
    npm: str,
    failures: list[str],
    warnings: list[str],
) -> None:
    mode = parse_e2e_mode()
    skip_reason = os.environ.get("RELEASE_E2E_SKIP_REASON", "").strip()

    if mode == "skip":
        if not skip_reason:
            failures.append("RELEASE_E2E_MODE=skip requires RELEASE_E2E_SKIP_REASON")
            return
        warnings.append(f"e2e smoke skipped by policy: {skip_reason}")
        return

    e2e_env = dict(os.environ)
    if env_truthy(e2e_env.get("RELEASE_E2E_HEADLESS")):
        e2e_env["HEADLESS"] = "1"

    code, output = run([npm, "run", "e2e:smoke"], cwd=FRONTEND, env=e2e_env)
    if code == 0:
        return

    if mode == "auto" and output_is_env_limited(output):
        reason = skip_reason or "environment limitation detected while running e2e smoke"
        warnings.append(f"e2e smoke degraded in auto mode: {reason}")
        warnings.append(f"e2e smoke raw error: {output}")
        return

    failures.append(f"e2e smoke failed: {output}")


def main() -> None:
    failures: list[str] = []
    warnings: list[str] = []

    for rel, label in [
        ("docker-compose.yml", "compose file"),
        ("Dockerfile", "api Dockerfile"),
        ("frontend/Dockerfile", "frontend Dockerfile"),
        ("alembic.ini", "alembic config"),
        ("alembic/env.py", "alembic env"),
        ("docs/deployment.md", "deployment guide"),
        ("docs/release-checklist.md", "release checklist"),
    ]:
        require_file(ROOT / rel, label, failures)

    docker_compose = shutil.which("docker-compose")
    if docker_compose is None:
        failures.append("docker-compose not installed")
    else:
        code, output = run([docker_compose, "config"])
        if code != 0:
            failures.append(f"docker-compose config failed: {output}")

        code, output = run([docker_compose, "version"])
        if code != 0:
            failures.append(f"docker-compose version failed: {output}")

    uv = shutil.which("uv")
    python = resolve_python()
    if python is None:
        failures.append("project python not available")
    else:
        code, output = run(
            [python, "-m", "pytest", "-q", "tests/test_api_main.py", "tests/test_provider_runtime.py", "tests/test_architecture.py"],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        )
        if code != 0:
            failures.append(f"python release tests failed: {output}")

    npm = shutil.which("npm")
    if npm is None:
        failures.append("npm not installed")
    else:
        code, output = run([npm, "run", "build"], cwd=FRONTEND)
        if code != 0:
            failures.append(f"frontend build failed: {output}")
        else:
            try:
                run_e2e_smoke(npm=npm, failures=failures, warnings=warnings)
            except ValueError as error:
                failures.append(str(error))

    for warning in warnings:
        print(f"[WARN] {warning}")

    if failures:
        print("Release check failed:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)

    print("Release check passed.")


if __name__ == "__main__":
    main()
