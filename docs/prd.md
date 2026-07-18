# Product Requirements Document — VetClaims Local

**Version:** 1.0 · **Method:** BMAD v6 · **Owner:** Daniel Neustadter · **Date:** 2026-07-18

## 1. Vision

A veteran runs one app on their own machine, feeds it their complete service and
medical record set, and receives a complete, correctly filled, ready-to-file VA
disability claim packet — with every AI suggestion cited back to a page in their
own records, and nothing ever leaving their hardware.

## 2. Problem

- Commercial claim-prep services (e.g. vetclaims.ai, ~$1,250 flat fee) require
  uploading decades of PII/PHI to a vendor cloud.
- Veterans routinely miss claimable secondary and presumptive conditions buried
  in hundreds of pages of service treatment records (STRs).
- The VA's own forms (21-526EZ et al.) are long, error-prone, and rating math
  (38 CFR §4.25/§4.26) is opaque, so veterans under-claim or file weak claims.
- Unaccredited paid "claim sharks" charge percentage fees; free tools are thin.

## 3. Users

Single persona for v1: **the self-hosting veteran** — technical enough to run an
installer/Ollama, preparing their own initial claim, increase, or appeal.
Single-tenant: one instance, one veteran's data.

## 4. Product principles

1. **Local-only.** No runtime network calls except to `localhost` Ollama. No telemetry.
2. **Cited or it doesn't ship.** Every extracted fact and suggested condition links to source document + page.
3. **Human in the loop.** Every AI output is an editable draft; nothing is auto-filed.
4. **Not a representative.** Prominent disclaimers; the veteran files via VA.gov themselves.
5. **The packet is the product.** Everything funnels into a printable/uploadable filing packet.

## 5. Functional requirements by epic

### Epic 1 — Foundation & walking skeleton
- FR1.1 Create/manage a claim case; upload PDF documents to it.
- FR1.2 Extract text from uploaded PDFs (native text layer; OCR later).
- FR1.3 Claimant profile form (identity, service, contact, direct deposit) — LLM pre-fill from records, human-editable, stored locally.
- FR1.4 Conditions list (name, onset, exposure basis) — human-editable.
- FR1.5 Generate filled **21-526EZ**, **21-4138**, **21-0966** PDFs from profile + conditions and download them.

### Epic 2 — Ingestion & case database
- FR2.1 OCR scanned pages; auto-detect text-layer vs image pages.
- FR2.2 Classify each document (STR, rating decision, DD-214, private treatment, DBQ, decision letter, other).
- FR2.3 Chunk + embed all text (sqlite-vec + nomic-embed-text); page-level provenance on every chunk.
- FR2.4 Structured extraction: service periods, deployments/exposures, diagnoses/complaints/injuries (date, provider, source page), current ratings.
- FR2.5 Merge extractions into a deduplicated condition timeline.

### Epic 3 — Analysis
- FR3.1 Suggest unclaimed conditions with in-service evidence, each with page citations.
- FR3.2 Suggest secondary conditions from a curated medical graph.
- FR3.3 Match presumptives (PACT Act, Agent Orange, Gulf War) from service era/locations.
- FR3.4 Combined-rating calculator (§4.25 table, §4.26 bilateral factor) + per-claim "what-if" upside.
- FR3.5 Evidence-gap checklist per candidate claim.

### Epic 4 — Drafting
- FR4.1 Personal statement per condition, grounded in extracted events with citations.
- FR4.2 Lay/buddy statement templates; nexus-letter outline for a physician.
- FR4.3 C&P exam prep sheet per condition (what the DBQ measures).
- FR4.4 Grounding checker: flag any draft sentence unsupported by the case database.
- FR4.5 All drafts editable in the UI before use.

### Epic 5 — Packet publisher
- FR5.1 Assemble full packet: filled 21-526EZ, statements as 21-4138s, bookmarked evidence PDF with per-condition index, filing checklist.
- FR5.2 Intent-to-File (21-0966) tracker with effective-date countdown.
- FR5.3 Field-perfect output verified against official form layouts.

### Epic 6 — Decisions & appeals
- FR6.1 Parse a VA decision letter → per-condition outcome + stated reasons.
- FR6.2 Recommend AMA lane (supplemental 20-0995 / HLR 20-0996 / Board 10182) with deadlines.
- FR6.3 Draft the chosen form + rebuttal statement targeting the denial reasons.

### Epic 7 — Hardening & distribution
- FR7.1 Single-user login; encryption at rest for the data directory.
- FR7.2 Encrypted backup/export/import.
- FR7.3 First-run wizard: Ollama check, model pull, refdata build.
- FR7.4 Docker Compose distribution; polished README with screenshots.

## 6. Non-functional requirements

- NFR1 Runs fully on a 16 GB VRAM GPU (RTX 4090 laptop); primary model fits in VRAM.
- NFR2 A 200-page record set ingests (OCR+extract) in under ~30 min on target hardware.
- NFR3 All LLM interchange is JSON-schema-constrained with validation/repair; drafting output passes grounding checks.
- NFR4 Works offline after models + refdata are present.
- NFR5 Test fixtures use fictional veterans only; repo never contains real PII/PHI.
- NFR6 Disclaimers on every screen footer and every generated document.

## 7. Out of scope (v1)

Multi-tenant/multi-user, VA API or e-filing integration, payments, human-review
marketplace, mobile apps, non-disability benefits (pension, education, GI Bill).

## 8. Success criteria

A full synthetic case (DD-214 + 40-page STR + prior rating decision) flows
end-to-end to a packet whose every 526EZ field is verified correct, and a
synthetic denial letter yields a correct appeal recommendation and filled
20-0996 — all with Ollama as the only external process.
