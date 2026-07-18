"""Single-worker job queue backed by the jobs table. Long work (text
extraction, LLM passes, packet builds) runs here so API requests return
immediately and the UI polls job status. One worker thread is enough for a
single-tenant app and serializes GPU use."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from typing import Callable

from sqlalchemy import select

from .. import models
from ..db import session

log = logging.getLogger("vetclaims.queue")

_HANDLERS: dict[str, Callable[[models.Job], dict | None]] = {}
_wake = threading.Event()
_stop = threading.Event()


def job_handler(job_type: str):
    def register(fn):
        _HANDLERS[job_type] = fn
        return fn
    return register


def enqueue(job_type: str, payload: dict) -> int:
    db = session()
    try:
        job = models.Job(type=job_type, payload=payload)
        db.add(job)
        db.commit()
        _wake.set()
        return job.id
    finally:
        db.close()


def set_progress(job_id: int, message: str) -> None:
    db = session()
    try:
        job = db.get(models.Job, job_id)
        if job:
            job.progress = message
            db.commit()
    finally:
        db.close()


def _run_one() -> bool:
    db = session()
    try:
        job = db.scalars(
            select(models.Job).where(models.Job.status == "queued")
            .order_by(models.Job.id)).first()
        if job is None:
            return False
        job.status = "running"
        db.commit()
        jid, jtype = job.id, job.type
    finally:
        db.close()

    result, error = None, None
    handler = _HANDLERS.get(jtype)
    if handler is None:
        error = f"no handler for job type {jtype!r}"
    else:
        try:
            db = session()
            try:
                result = handler(db.get(models.Job, jid))
            finally:
                db.close()
        except Exception:
            error = traceback.format_exc()
            log.exception("job %s (%s) failed", jid, jtype)

    db = session()
    try:
        job = db.get(models.Job, jid)
        job.status = "error" if error else "done"
        job.error = error
        job.result = result
        db.commit()
    finally:
        db.close()
    return True


def _loop() -> None:
    # reset jobs orphaned by a previous crash/restart
    db = session()
    try:
        for job in db.scalars(select(models.Job).where(models.Job.status == "running")):
            job.status = "queued"
        db.commit()
    finally:
        db.close()
    while not _stop.is_set():
        try:
            if not _run_one():
                _wake.wait(timeout=2.0)
                _wake.clear()
        except Exception:
            log.exception("queue loop error")
            time.sleep(2)


def start_worker() -> None:
    threading.Thread(target=_loop, name="vetclaims-worker", daemon=True).start()


def stop_worker() -> None:
    _stop.set()
    _wake.set()
