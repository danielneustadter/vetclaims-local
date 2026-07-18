# Epics & Stories — VetClaims Local (BMAD v6)

Status legend: ⬜ todo · 🟨 in progress · ✅ done

## Epic 1 — Foundation & walking skeleton ✅
- ✅ S1.1 Repo scaffold, BMAD docs, GitHub publish
- ✅ S1.2 Backend skeleton: FastAPI app, SQLite models, job queue, health endpoint
- ✅ S1.3 Case + document upload API; native PDF text extraction (PyMuPDF)
- ✅ S1.4 Ollama client with schema-constrained JSON + repair retry
- ✅ S1.5 Claimant profile: API + LLM pre-fill from uploaded docs (two-pass:
  identity+service, then conditions; completeness-scored period merge)
- ✅ S1.6 VA form templates: download 21-526EZ / 21-4138 / 21-0966, build field maps
- ✅ S1.7 Form fill service + download endpoints (pypdf AcroForm, XFA dropped,
  pdfium render verification)
- ✅ S1.8 Frontend shell: dashboard, documents, profile, conditions, forms pages
- ✅ S1.9 End-to-end walkthrough in browser, screenshots, push

Known follow-ups from verification: unlabeled radio groups (branch of service,
ITF benefit type, homeless Y/N) left unfilled pending the S5.4 visual
field-verification pass; 526EZ conditions cap at 15 rows (addendum sheet in
Epic 5).

## Epic 2 — Ingestion & case database
- ⬜ S2.1 OCR pipeline (image-page detection + OCR engine)
- ⬜ S2.2 Doc-type classifier (fast model)
- ⬜ S2.3 Chunk + embed into sqlite-vec with page provenance
- ⬜ S2.4 Structured extraction jobs → medical_event/service_period/existing_rating
- ⬜ S2.5 Merge pass → condition timeline UI
- ⬜ S2.6 Synthetic fixture cases + extraction-recall tests

## Epic 3 — Analysis
- ⬜ S3.1 Refdata: eCFR 38 CFR Part 4 → rating_schedule.json
- ⬜ S3.2 Combined-rating math (§4.25/§4.26) + unit tests
- ⬜ S3.3 Secondary graph + presumptives datasets
- ⬜ S3.4 Condition finder + suggestions API/UI with citations
- ⬜ S3.5 What-if rating projections + evidence-gap checklist

## Epic 4 — Drafting
- ⬜ S4.1 Personal statement generator (grounded, cited)
- ⬜ S4.2 Lay statement + nexus outline + C&P prep generators
- ⬜ S4.3 Grounding checker job
- ⬜ S4.4 Draft editor UI

## Epic 5 — Packet publisher
- ⬜ S5.1 Multi-condition 526EZ fill from case DB
- ⬜ S5.2 Evidence PDF: bookmarked, per-condition indexed
- ⬜ S5.3 Packet assembly + filing checklist + ITF tracker
- ⬜ S5.4 Field-verification pass against official forms

## Epic 6 — Decisions & appeals
- ⬜ S6.1 Decision letter parser
- ⬜ S6.2 AMA lane recommender + deadlines
- ⬜ S6.3 Appeal form fill (20-0995 / 20-0996 / 10182) + rebuttal drafts

## Epic 7 — Hardening & distribution
- ⬜ S7.1 Auth + encryption at rest + backup/export
- ⬜ S7.2 First-run wizard
- ⬜ S7.3 Docker Compose + docs + screenshot gallery
