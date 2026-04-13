# Hybrid-Agent Coding Conventions

## Python
- **Docstrings**: Every module, class, and function in `src/hybrid_agent` must use Google style docstrings. Include `Args`, `Returns`, and `Raises` sections where applicable; link to type hints when possible.
- **Type annotations**: Annotate all function arguments and return values. Prefer `typing.TypedDict`/`dataclasses` for structured data. Use `Path`/`Env` wrappers instead of raw strings for filesystem paths.
- **Imports**: Use explicit imports only. `import *` is forbidden. Third-party modules should be grouped (std lib → third-party → local) and each block separated by a blank line.
- **Dependency direction**: API routes in `src/hybrid_agent/api/routes` must not import `core.database` or any repository-level modules; they should call `core.rag_system`, service helpers, or `agent` builders. `core/` modules must not import `agent/`.
- **Configuration**: `dotenv` values should be read via helper functions (`core/config.py`). Avoid hard-coded secrets; reference `ENV` names such as `API_KEY`, `CHROMA_DB_DIR`, etc.
- **Execution**: Always launch Python via `uv run ...` so we capture the sanctioned dependency graph. Do not run `python -m uvicorn ...` directly when invoking the FastAPI app.

## Frontend (Vue + Streamlit)
- **Vue**: All new Vue code lives under `frontend/`. Use `<script setup>` and the Composition API. Files should be PascalCase. Shared state belongs in Pinia stores, never in standalone modules that import backend code.
- **Streamlit**: The existing UI under `src/hybrid_agent/web/` is purely for demos. It may import from `core/` but still must follow Python docstring and type-hint rules.
- **HTTP contracts**: The Vue 3 frontend under `frontend/` must fetch data through `/api/*` endpoints with Axios interceptors handling auth headers. The Streamlit demo under `src/hybrid_agent/web/` currently imports `core/` services directly rather than relying on HTTP, which reflects today’s single-tenant execution path.

## CSS & Assets
- **Variable-driven theming**: Favor CSS variables for colors, spacing, and elevation. Avoid hard-coded hex values; instead define them in `frontend/src/assets/tokens.css` (once M10 begins).
- **Spacing & Layout**: Use utility classes for consistent gaps. Do not mix layout logic into inline styles.
- **Icons & Typography**: Prefer icon components when possible; choose expressive type pairings (sans serif headings, serif/mono for data). Avoid default stacks like Arial without rationale.

## Governance
- **Document changes**: Any update to architecture or conventions must be called out in `docs/architecture.md`, `docs/conventions.md`, and `claude-progress.txt` before proceeding to the next module.
- **Checks**: Locally run `uv run ruff check src/ --output-format=concise`, `uv run mypy src/hybrid_agent/ --ignore-missing-imports`, and `uv run pytest tests/ --tb=short -q`. Respect failures; fixing them keeps the harness workflow clean.
- **Formats**: Code should be formatted via `ruff format` or `black` (as configured in `pyproject.toml`). Do not mix formatting tools without CI alignment.

## Provider Runtime Harness Rules
- **Contract-first tests**: For provider runtime changes, update tests before implementation merge: `tests/test_provider_runtime.py` and `tests/test_api_main.py` must cover route mount/bridge and `model_used` contract.
- **`model_used` contract**: Successful non-stream `/api/v1/chat` responses must include `model_used` as a non-empty string. If runtime provider metadata is unavailable, fallback labeling is allowed temporarily.
- **`/api/v1/models` contract**: Endpoint must return a non-empty list with at least `id`, `name`, and `description` string fields per item. Additional provider metadata fields are additive and backward-compatible.
- **Provider health checks**: `POST /api/v1/providers/{provider_id}/health` must degrade gracefully. Failures should return a structured `ok/error/latency_ms` payload instead of surfacing raw stack traces to the frontend.
- **Legacy compatibility**: `/api/models` must remain a bridge to `/api/v1/models` until explicit deprecation is announced in docs and progress notes.
- **Browser smoke guard**: `tests/e2e/smoke.spec.js` should keep at least one API-level assertion for `/api/v1/models` to catch frontend-backend contract drift early.

## Phase 4 Batch B UI Rules
- **Permission-first navigation**: Frontend navigation and route guards should hide or redirect away from admin-only views before the user triggers a backend `403`.
- **Readonly settings for non-managers**: Users without `admin`/`group_admin` should still be able to view provider state, but destructive or mutating controls must be hidden or disabled in the UI.
- **Monitoring scaffolds are code**: Grafana dashboard JSON and Prometheus rule files are part of the repo harness and must be kept declarative and provisionable from `docker-compose.yml`.

## References
- `docs/superpowers/specs/2026-04-12-enterprise-upgrade-design.md` explains the M0 requirements and future phases.
- `README.md`, `docs/project-overview.md`, and `QUICKSTART.md` cover environment setup; do not contradict them when updating conventions.
