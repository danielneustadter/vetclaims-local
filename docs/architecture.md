# Architecture — VetClaims Local

**Version:** 1.0 · **Method:** BMAD v6 · **Date:** 2026-07-18

## 1. System overview

```
┌─────────────┐   HTTP   ┌──────────────────────────────┐   HTTP   ┌─────────┐
│ React SPA    │ ───────► │ FastAPI backend               │ ───────► │ Ollama  │
│ (Vite, 5173) │          │ (uvicorn, 8600)               │ :11434   │ GPU     │
└─────────────┘          │  ├ routers    (REST API)      │          └─────────┘
                         │  ├ ingest     (OCR, classify) │
                         │  ├ extract    (case database) │
                         │  ├ analysis   (conditions,    │
                         │  │             ratings)       │
                         │  ├ drafting   (statements)    │
                         │  ├ packet     (PDF publisher) │
                         │  ├ llm        (client, queue) │
                         │  └ refdata    (38 CFR, etc.)  │
                         └──────────┬───────────────────┘
                                    ▼
                         data/  (gitignored, local only)
                          ├ vetclaims.db   SQLite + sqlite-vec
                          ├ uploads/       original PDFs
                          └ output/        generated packets
```

No external network calls at runtime. Ollama at `localhost:11434` is the only
out-of-process dependency.

## 2. Backend

- **FastAPI + SQLAlchemy 2 + SQLite.** Single-file DB in `data/`. `sqlite-vec`
  extension for embeddings (no separate vector DB).
- **Job queue:** in-process `asyncio` worker consuming a `jobs` table
  (id, type, payload JSON, status, progress, result JSON, error). Long work
  (OCR, extraction, drafting) always goes through a job; the UI polls
  `GET /api/jobs/{id}`.
- **LLM layer** (`app/llm/`): thin Ollama HTTP client. Two lanes from config:
  `primary` (default `mistral-small:22b` — fits 16 GB VRAM) and `fast`
  (default `qwen3:4b`) plus `embed` (`nomic-embed-text`). All non-drafting
  calls use Ollama's `format: <json-schema>` constrained decoding, validated by
  Pydantic, with one repair retry. Big documents are processed map-reduce:
  per-chunk extraction → merge pass.
- **PDF engine** (`app/packet/`): official VA form templates (AcroForm under an
  XFA layer — the XFA is dropped, same approach as e2096-platform). Filling via
  `pypdf.update_page_form_field_values`; preview rendering via `pypdfium2`;
  overlays (watermarks on drafts, evidence-index pages) via `reportlab`.

## 3. Data model (core tables)

- `case` — one claim case (v1: single row in practice).
- `document` — uploaded file, sha256, doc_type, page_count, ocr_status.
- `page` — per-page text + text_source (native|ocr).
- `chunk` — text chunk, embedding (vec), document_id, page_span.
- `claimant_profile` — 526EZ identity/service/payment fields (one per case).
- `service_period`, `medical_event` (diagnosis/complaint/injury/treatment;
  date, provider, icd, source document+page), `existing_rating`.
- `condition` — a tracked (candidate or claimed) condition; links to
  `medical_event` evidence rows; status: suggested|selected|claimed|granted|denied.
- `draft` — generated document (type, condition_id?, markdown, grounding report).
- `job` — queue rows.

## 4. Frontend

React 18 + TypeScript + Vite. Plain fetch + polling (no websockets in v1).
Pages: Dashboard (case status, pipeline progress), Documents (upload/list/page
viewer), Profile (526EZ fields), Conditions (suggestions + evidence + what-if
rating), Drafts (editor), Packet (assemble/download), Decision (appeals).
Disclaimer banner in the app shell footer, every page.

## 5. Reference data (`backend/app/refdata/` + `scripts/`)

Built by scripts into versioned JSON shipped with the repo:
`rating_schedule.json` (38 CFR Part 4 diagnostic codes, parsed from eCFR API),
`combined_ratings` (pure functions, not data), `presumptives.json`,
`secondary_graph.json`, `dbq_map.json`, and `forms/*.pdf` + `forms/*.map.json`
(official templates + field name maps).

## 6. Key decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | SQLite (+sqlite-vec), not Postgres | zero-install self-hosting; single-tenant scale |
| D2 | In-process asyncio job queue | no Redis/Docker on host; jobs table gives restartability |
| D3 | Ollama over vLLM | native Windows support, model management UX |
| D4 | `mistral-small:22b` default primary | already on machine, 12 GB fits 16 GB VRAM fully |
| D5 | Schema-constrained JSON for all extraction | reliability on mid-size local models |
| D6 | pypdf AcroForm fill, XFA dropped | proven in e2096-platform on the same form family |
| D7 | Map-reduce over long context | KV-cache VRAM limits; per-doc extraction merges cleanly |

## 7. Ports & processes (dev)

- backend: `uvicorn app.main:app --port 8600` (from `backend/`)
- frontend: Vite dev server on 5173, proxying `/api` → 8600
- Ollama: `localhost:11434`
