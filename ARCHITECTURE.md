# Architecture Overview

This monorepo hosts a FastAPI backend and an Umi/React frontend that together power an AI-assisted writing platform with RAG-enhanced knowledge management. The sections below summarize the key architectural decisions, runtime topology, and the main flows that tie the system together.

## Repository Layout

- `backend/`: FastAPI service, SQLAlchemy models, LangChain-powered services, Alembic migrations, Docker assets.
- `frontend/`: Umi Max single-page application with Ant Design UI, AI editor integrations, and domain-specific pages.
- Root-level `Dockerfile`, `package.json`, and `pnpm-lock.yaml` enable containerized full-stack deployments.

## Backend Architecture (FastAPI + SQLAlchemy)

### Runtime & Configuration

- Application entry is `backend/app/main.py`. A custom FastAPI lifespan hook configures logging, creates DB tables, seeds system knowledge bases, spawns the RAG worker thread, and resumes unfinished writing tasks at startup.

```94:150:backend/app/main.py
def create_tables():
    try:
        Base.metadata.create_all(bind=sync_engine)
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"创建数据库表时出错: {str(e)}")
        logger.exception("详细错误信息:")

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    ...
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
...
```

- `app/config.py` blends `.env` variables with `config.yaml`, defining MySQL DSNs, model endpoints, RAG limits, and writing constraints in a single `Settings` object loaded via `pydantic-settings`.
- `app/database.py` exposes both sync (`sync_session`) and async (`async_session`) engines, enabling transactional REST handlers alongside asyncio-based background jobs.

### Persistence & Domain Models

- SQLAlchemy declarative models live under `app/models/`. Key aggregates:
  - `user.py`, `department.py`, and `system_config.py` encode identity, RBAC flags, and tenant metadata.
  - `document.py` and `chat.py` track editable documents, version history, chat sessions/messages, and the linkage between AI runs and stored content.
  - `outline.py` defines hierarchical `Outline` → `SubParagraph` trees with reference metadata, plus reusable `WritingTemplate` rows.
  - `task.py` captures long-running operations (outline/content generation) with JSON-serialized parameters/results and progress logging.
  - `rag.py` stores knowledge-base definitions (`RagKnowledgeBase`) and ingestion state for uploaded files (`RagFile` with rich status enums).

### API Surface

Routers reside in `app/routers/v1/` and are grouped by domain:

- `auth.py` issues JWTs, hashes passwords, and provisions per-user knowledge bases during registration.
- `users.py` (not shown above) manages user/org metadata.
- `document.py` implements CRUD with optimistic versioning, docx/pdf exports via `utils/document_converter.py`, and linkage to chat sessions.
- `writing.py` is the largest router, coordinating outline generation, paragraph drafting, reference management, task orchestration, and streaming results to the UI.
- `rag.py` handles knowledge-base CRUD: file uploads (with deduplication, format conversion, and async ingestion), permission checks across system/department/personal scopes, chat entrypoints, and file lifecycle operations.

All routers return a common `APIResponse` envelope (`app/schemas/response.py`) to keep the frontend contract uniform.

### AI Writing & Task Pipeline

- `app/services/langchain_service.py` wraps LangChain `ChatOpenAI` clients, centralizes prompt templates for outline/paragraph/full-text generation, and coordinates optional RAG context + web search. It persists incremental status updates to `Task` rows so the UI can surface progress bars and logs.
- `routers/v1/writing.py` schedules long-running work via a module-level `ThreadPoolExecutor`, guarded by `running_tasks`/`task_lock`. It creates chat sessions/messages (`models/chat.py`), seeds `Task` rows, and uses service callbacks to stream completions back to the client.
- Utilities such as `app/parser.py` (PDF/DOCX/Markdown parsing and outline extraction) and `app/utils/outline.py` (tree builders, reference serialization) keep the routers lean.

### RAG Ingestion Worker

- The knowledge ingestion loop lives in `app/rag/process.py`. On startup, `rag_worker()` spins a dedicated asyncio event loop with concurrent coroutines for:
  - polling eligible `RagFile` rows and staging them into queues (`rag_content_queue`, `rag_summary_queue`, `rag_upload_queue`, `rag_parsing_queue`),
  - uploading chunks to the external knowledge service via `rag_api_async`,
  - monitoring remote parsing status until `DONE`/`FAILED`,
  - rolling back in-progress statuses if the process restarts unexpectedly.
- Permissions and KB selection helpers are centralized in `app/rag/kb.py`, ensuring consistent access control when routers or workers modify knowledge assets.

### Document Conversion & Export

- `app/utils/document_converter.py` converts stored HTML into styled DOCX/PDF artifacts. It injects localized numbering schemes, rebuilds tables, and fixes heading levels before streaming files back through `document.py` endpoints.

### Infrastructure & Ops

- Alembic migrations (`backend/alembic/versions/*.py`) track schema evolution.
- `backend/Dockerfile` plus `docker-compose.yml` wire up the FastAPI app, MySQL, and nginx.
- `requirements.txt` pins FastAPI, SQLAlchemy, LangChain, parsing libraries, etc.

## Frontend Architecture (Umi Max + Ant Design)

### Stack & Runtime Hooks

- The SPA is scaffolded with `@umijs/max` (Umi v4). Global runtime customizations live in `src/app.ts`, where `window.fetch` is monkey-patched to inject JWT headers, rewrite `/api/v1/completions` payloads based on embedded `<content>` markers, and auto-toggle specific `action` flags for abridge/rewrite/extension flows.
- `getInitialState` seeds layout data; optional iframe embedding is detected early to adjust authentication and behavior.

### Routing & Layout

- `src/routes.ts` declares route-to-page mappings. Each feature (Login, AiChat, WritingAssistant, knowledge libraries, admin panels, etc.) is implemented as a directory under `src/pages/`.
- Most screens are standalone pages rather than nested layouts, simplifying SSR and code splitting managed by Umi.

### State & Data Access

- Lightweight page-level models (`src/pages/EditorPage/model.ts`) leverage Umi’s `useModel` API for shared state (e.g., the currently loaded document).
- `src/utils/fetch.ts` exports `fetchWithAuth`, `fetchWithAuthNew`, and `fetchWithAuthStream` helpers. They normalize base URLs (`src/config.ts`), enforce token headers, surface toast errors via Ant Design’s `message`, and provide stream-friendly variants for SSE responses.
- Global tokens/admin flags are persisted in `localStorage` to survive reloads and power iframe embedding flows kicked off from third-party portals.

### Key Feature Modules

- **Writing workspace (`pages/EditorPage`)**  
  - Wraps the third-party `<AiEditor>` component, synchronizes content via debounced PUTs to `/api/v1/documents/{doc_id}`, and mirrors the editor’s outline into a tree for navigation.  
  - Integrates modals for version history (`components/VersionHistory`), knowledge-file uploads, and AI side panels.  
  - Uses query parameters (`document_id`, `user_id`, `id`) to drive read-only modes and to correlate AI chat sessions with document tabs.

- **AI chat & retrieval (`pages/AiChat`)**  
  - Builds on `@ant-design/x` chat primitives. Chat sessions are persisted via `/api/v1/rag/chat/session`, models are fetched from `/api/v1/models`, and streaming answers are rendered through `XStream`.  
  - Users can attach files from `KnowledgeSearch`, upload new references, preview attachments, and toggle “enhanced search” flags stored in localStorage for continuity.

- **Knowledge management suites (`SystemKnowledge`, `DepartKnowledge`, `PersonalKnowledge`, `TemplateManage`, etc.)**  
  - Each page orchestrates specific backend routers (e.g., `rag.py` endpoints for file ingestion and `writing.py` for template reuse).  
  - Shared primitives like `components/FileUpload` and `hooks/useFilePreview` provide consistent UX for browsing RagFiles and rendering document previews inline.

- **WritingAssistant & WritingHistory**  
  - Act as entrypoints for initiating AI-assisted drafts and browsing past sessions, respectively, routing users into `EditorPage` or `AiChat` with the correct query params.

### UI & Styling

- Ant Design v5 drives the component library, complemented by `@ant-design/pro-components` for admin-esque grids.
- Styles combine `.less` modules (scoped per page/component) with global overrides in `src/overrides.less`.
- Media (logos, icons) lives under `src/assets` and `public/`, enabling white-labeling without code changes.

## Cross-Cutting Concerns & Data Flow

1. **Authentication**: Users log in via `/api/v1/token` (FastAPI OAuth2), store JWTs client-side, and every `fetchWithAuth*` call injects the token in `Authorization: Bearer ...`.
2. **Document lifecycle**: The frontend creates documents, edits content in AiEditor, and relies on `/api/v1/documents` endpoints for persistence and exporting. Background AI services drop generated outlines/content into chat sessions tied to those document IDs.
3. **Knowledge ingestion**: Uploads from the UI hit `/api/v1/rag/files`, which write temp files, deduplicate via SHA-256, and queue ingestion. The asynchronous worker pushes files to the external RAG API, polls status, and exposes ready-to-use file metadata back to the UI.
4. **AI generation loops**: Whether drafting an outline or chatting against the KB, FastAPI orchestrates LangChain calls with optional RAG context, logs incremental progress to `tasks`, and streams responses to the frontend via SSE or polling, depending on the endpoint.

## Deployment & Operations

- Backend: Run `uvicorn app.main:app` behind nginx (see `backend/nginx.conf`). Docker assets expect environment variables or `config.yaml` for DB + model endpoints.
- Frontend: `pnpm install` + `pnpm dev` (or `max build`) builds the Umi SPA; `frontend/Dockerfile` can serve the compiled bundle via nginx.
- The repo ships `sqls/` snapshots for manual data fixes and `memory-bank/` docs that capture product context for onboarding.

## Suggested Next Steps for Contributors

- Keep architectural parity updated here when adding routers, models, or major UI modules.
- Document any new background jobs or queue consumers to aid ops in sizing worker pools.
- Ensure front-end routes that depend on query parameters document their contract (e.g., `document_id`, `user_id`) to maintain deep-link stability.

