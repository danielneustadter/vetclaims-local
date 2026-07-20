import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .llm.queue import start_worker, stop_worker

# handler registration side effects
from .ingest import textract  # noqa: F401
from .extract import prefill, case_extract, decisions  # noqa: F401
from .drafting import generate as _draft_gen  # noqa: F401

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_worker()
    yield
    stop_worker()


app = FastAPI(title="VetClaims Local", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import (analysis, appeals, cases, casefile,  # noqa: E402
                      conditions, documents, drafts, jobs, packet)

app.include_router(analysis.router)
app.include_router(appeals.router)
app.include_router(drafts.router)
app.include_router(cases.router)
app.include_router(casefile.router)
app.include_router(documents.router)
app.include_router(conditions.router)
app.include_router(jobs.router)
app.include_router(packet.router)
