"""Structure guards for Harness Engineering M0."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _collect_imported_modules(filepath: Path) -> set[str]:
    """Return every module name imported by the given file."""

    tree = ast.parse(filepath.read_text())
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = ("." * node.level) + (node.module or "")
            if module_name:
                modules.add(module_name)
    return modules


def _normalize_module(module_name: str) -> list[str]:
    """Strip leading dots and split the module into path segments."""

    stripped = module_name.lstrip(".")
    return stripped.split(".") if stripped else []


def _module_mentions_segment(module_name: str, segment: str) -> bool:
    return segment in _normalize_module(module_name)


def test_api_routes_do_not_import_repositories() -> None:
    """API routes must only depend on services, not repositories."""

    violations: list[str] = []
    api_routes_dir = PROJECT_ROOT / "src" / "hybrid_agent" / "api" / "routes"

    for route in api_routes_dir.rglob("*.py"):
        for module_name in _collect_imported_modules(route):
            if _module_mentions_segment(module_name, "repositories"):
                violations.append(
                    f"{route}: imports repository module '{module_name}' directly",
                )

    assert not violations, (
        "API routes must not import repositories directly; wrap repository calls in services.\n"
        + "Violations:\n"
        + "\n".join(violations)
    )


def test_core_does_not_import_agent() -> None:
    """core/ must not depend on agent/ to preserve the directed graph."""

    violations: list[str] = []
    core_dir = PROJECT_ROOT / "src" / "hybrid_agent" / "core"
    allowed_agent_imports = {
        "hybrid_agent.agent.reviewer",
    }

    for core_file in core_dir.rglob("*.py"):
        for module_name in _collect_imported_modules(core_file):
            if _module_mentions_segment(module_name, "agent"):
                normalized = _normalize_module(module_name)
                if not normalized:
                    continue
                if normalized[0] == "agent" or normalized[:2] == ["hybrid_agent", "agent"]:
                    if module_name in allowed_agent_imports:
                        continue
                    violations.append(
                        f"{core_file}: imports agent module '{module_name}'",
                    )

    assert not violations, (
        "core/ components must not import agent/ modules to avoid reversed dependencies.\n"
        + "Violations:\n"
        + "\n".join(violations)
    )
