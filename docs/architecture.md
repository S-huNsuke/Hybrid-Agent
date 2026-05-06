# Hybrid-Agent Architecture Notes

## 1. Current Landscape
- **Backend** is a FastAPI service defined in `src/hybrid_agent/api/main.py`. Primary routes are versioned under `/api/v1`, with legacy `/api/*` bridges retained for compatibility. JWT auth, RBAC, provider management, document upload tasks, and chat session endpoints are already mounted.
- **Core services** live under `src/hybrid_agent/core/`. They include `document_processor`, `hybrid_retriever` (BM25 + vector + HyDE), `vector.py` (Chroma wrapper), `rag_system` (document ingestion), and supporting utilities such as `session_manager`.
- **Agent layer** (`src/hybrid_agent/agent/`) hosts the LangGraph-based `agentic_rag_graph` plus `builder`. API chat still mixes `RAGSystem` and Agent paths, but model/runtime selection is now shared through the LLM selector contract.
- **Web UI** is a Vue 3 SPA under `frontend/`, communicating with the FastAPI backend exclusively via HTTP/Axios. There is no longer a Python-side web module.
- **CLI** entrypoints in `main.py` and `src/hybrid_agent/cli/` provide alternative interfaces to the same backend logic.

## 2. Logical Layers and Data Flow
```
Vue 3 SPA (frontend/)   CLI
       ↓                  ↓
   API layer (/api/v1/*) ← FastAPI
       ↓
   Service layer (core/ + agent/)  ← manages documents, vector store, hybrid retrieval
       ↓
   Persistence layer (DATABASE_URL / SQLite fallback + Chroma collection)
```
- `core/` exposes retrieval services (BM25 + Chroma + HyDE) and document management while remaining independent of API routing.
- `agent/` orchestrates advanced reasoning flows but must not be imported from `core/` (relationship is unidirectional: `agent` consumes `core`, not vice versa).
- API routes consume services in `core/` (and eventually `agent/`), but must not directly depend on ORM or the low-level SQLite file.
- `frontend/` communicates with FastAPI endpoints via HTTP/Axios and never imports Python modules from `src/`.

## 3. Dependency Constraints
- `core/` must not import from `agent/` except for the whitelisted case `hybrid_agent.agent.reviewer` used by `core/reranker.py` (see `tests/test_architecture.py`). This ensures the directed dependency graph remains enforceable.
- `api/` routes must not reach into `core/database.py` or any repository-level module; they should only call service helpers (`rag_system`, `document_processor`, etc.).
- `cli/` should continue to consume public entrypoints rather than low-level internals.
- `frontend/` interacts through HTTP routes exclusively and never imports Python modules.
- `docs/conventions.md` defines naming, docstring, and type-annotation expectations that cut across layers.

## 4. Operational Notes
- FastAPI app is launched via `uv run uvicorn hybrid_agent.api.main:app ...` with CORS explicitly allowing localhost pairs. There is no `uvicorn` supervisor yet, so use `uv` for consistency.
- Vue 3 frontend is launched via `cd frontend && npm run dev` or via `./start.sh` which boots both backend and frontend together.
- CLI entrypoint `main.py` uses `HybridAgent` class (not yet fully synced with new agentic graph).
- Tests cover query understanding, RRF merging, session management, and the existing architecture guard in `tests/test_architecture.py`, which enforces the `core` → `agent` boundary with a reviewer whitelist.

## 5. Known Gaps vs. Plan
- Browser-side Playwright smoke exists, but full browser-level acceptance and deployment rehearsal are not yet part of a repeatable local script.
- Agentic RAG graph is not the universal default path; some API flows still use `RAGSystem` directly.
- Monitoring has provisioning and baseline rules/dashboard, but not yet a mature business dashboard set.
- Frontend bundle size is still large and lacks code-splitting optimization.

Documenting these gaps here keeps future contributors aware of the divergence between the current repo and the target enterprise spec.

## 6. Provider Runtime Integration Status (2026-04-13)
- `/api/v1/chat` now routes both RAG and Agent flows through the same runtime-selection contract, and successful responses surface a non-empty `model_used`.
- `/api/v1/models` is now built from runtime-visible provider records plus environment fallbacks, while keeping the minimum `id/name/description` contract stable.
- Provider CRUD is complemented by `POST /api/v1/providers/{provider_id}/health`, which performs a lightweight `/models` probe against the configured provider endpoint and returns `ok/latency_ms/error`.
- Settings UI consumes the same provider/runtime surface and can trigger health checks without leaving the page.

## 7. Phase 4 Batch B Status (2026-04-13)
- **P4 Permission UX:** sidebar navigation now hides admin routes for non-admin users, router guards prevent direct `/admin` access, and `AdminView` renders a UI-level access-denied state instead of forcing users into backend `403` responses.
- **P5 Provider Productization:** settings page exposes provider health checks, runtime model feedback stays visible in chat, and provider management actions are hidden for unauthorized users.
- **P6 Monitoring Bootstrap:** Prometheus now loads rule files from `prometheus/rules/*.yml`, while Grafana provisions a baseline dashboard from `grafana/provisioning/dashboards/`.

## 8. Phase 4 Batch A Status (2026-04-13)
- **M20 Browser E2E:** Playwright harness now boots isolated frontend/backend services, uses a dedicated E2E SQLite database, and the full smoke path `register -> provider -> user -> upload -> chat` has completed successfully in the current environment.
- **M21 Provider Runtime UX:** `/api/v1/auth/me` now returns role metadata used by the frontend permission layer, so browser-visible provider/admin capabilities match backend authorization.
- **M22 Document UX:** documents workspace supports multi-file upload, task progress cards, retry flows, and client-side search/filter/sort from the primary page state.
- **M25 Frontend Performance:** router views are lazy-loaded and Vite chunking now splits app/vendor/page assets instead of shipping a single monolithic bundle.

## 9. Release Hardening Status (2026-04-13)
- **Container startup chain:** API image now includes Alembic files and starts through `docker-entrypoint.sh`, which runs `alembic upgrade head` before `uvicorn`.
- **Compose readiness:** `docker-compose.yml` now includes health-aware dependencies, backup service wiring, Prometheus rules, Grafana provisioning, and frontend/api runtime env alignment.
- **Release validation:** `scripts/release_check.py` validates compose rendering, Python regression suite, and frontend build in one pass.
- **Operational docs:** `docs/deployment.md` and `docs/release-checklist.md` document startup, migration, backup/restore, and release acceptance flow.
- **Current blocker:** the repository is code-ready for `M23`, but this machine cannot perform `docker-compose up -d` because Docker daemon access is unavailable.

### Runtime Harness Coverage
- `tests/test_api_main.py` verifies route mounting and legacy bridge parity for `/api/models` -> `/api/v1/models`.
- `tests/test_provider_runtime.py` verifies `model_used` passthrough and fallback contract for `/api/v1/chat`, minimum `/api/v1/models` response shape, and provider health probe behavior.
- `tests/e2e/smoke.spec.js` includes browser-side smoke checks for `/api/v1/models` contract alongside the login/upload/chat flow.
