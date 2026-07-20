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

## Epic 2 — Ingestion & case database ✅
- ✅ S2.1 OCR pipeline — RapidOCR (pure-pip ONNX, offline) on pages without a text layer
- ✅ S2.2 Doc-type classifier (fast model, falls back to primary)
- ✅ S2.3 Chunk + embed into sqlite-vec with page-span provenance + search endpoint/UI
- ✅ S2.4 Structured extraction job → medical_event + existing_rating with page citations
- ✅ S2.5 LLM merge pass (18→10 condition groups on fixture case) + Case File timeline UI
- ✅ S2.6 Fixture case incl. scanned page + rating decision; extraction-recall test
  (gated by VETCLAIMS_LLM_TESTS=1; 8/8 passing incl. live-LLM recall)

## Epic 3 — Analysis ✅
- ✅ S3.1 Refdata: eCFR API → rating_schedule.json (724 DCs, 421 with tiers,
  §4.130 mental-disorder formula attached to 9xxx codes)
- ✅ S3.2 Combined-rating math (§4.25 table + §4.26 bilateral factor) — pure
  functions tested against the regulation's published examples
- ✅ S3.3 Curated secondary graph (23 edges w/ nexus rationale), presumptives
  (PACT/AO/Gulf War/Lejeune/radiation), DBQ map, DC override table
- ✅ S3.4 Deterministic condition finder: direct (cited), secondary,
  presumptive-eligibility — Analysis tab with add-to-claim
- ✅ S3.5 What-if projections at min/max tier + evidence-gap checklist per candidate

Follow-up: spine codes (5235-5243) share the spine General Rating Formula —
attach its tiers like the mental formula (affects low-back what-if).

## Epic 4 — Drafting ✅
- ✅ S4.1 Personal statement generator — only free-text LLM output in the app;
  built strictly from the condition's cited events + profile facts
- ✅ S4.2 Nexus outline (physician handout w/ evidence block + graph rationale),
  C&P prep sheet (DBQ + actual rating tiers), lay-statement template — all
  deterministic, no LLM
- ✅ S4.3 Grounding checker: structured verification pass flags unsupported
  factual sentences (verified: caught an invented symptom sentence on fixture)
- ✅ S4.4 Drafts tab with editor, grounding flags, save; Forms tab loads
  reviewed statements into the 21-4138

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
