"""Optional single-user passphrase gate. Off until a passphrase is set (the
app is localhost-only by default). When enabled, every /api route except
health and auth requires the X-Auth-Token header from a successful login.

At-rest encryption is intentionally delegated to the OS (BitLocker/FileVault/
LUKS) — documented in the README — rather than shipping a half-measure."""

from __future__ import annotations

import hashlib
import json
import secrets

from fastapi import HTTPException, Request

from .config import settings

_AUTH_FILE = settings.data_dir / "auth.json"
_TOKENS: set[str] = set()

_ITERATIONS = 300_000


def _hash(passphrase: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt,
                               _ITERATIONS).hex()


def enabled() -> bool:
    return _AUTH_FILE.exists()


def setup(passphrase: str) -> None:
    if enabled():
        raise HTTPException(400, "passphrase already set")
    if len(passphrase) < 8:
        raise HTTPException(400, "passphrase must be at least 8 characters")
    salt = secrets.token_bytes(16)
    _AUTH_FILE.write_text(json.dumps(
        {"salt": salt.hex(), "hash": _hash(passphrase, salt)}))


def login(passphrase: str) -> str:
    if not enabled():
        raise HTTPException(400, "no passphrase set")
    data = json.loads(_AUTH_FILE.read_text())
    if not secrets.compare_digest(
            _hash(passphrase, bytes.fromhex(data["salt"])), data["hash"]):
        raise HTTPException(401, "wrong passphrase")
    token = secrets.token_urlsafe(32)
    _TOKENS.add(token)
    return token


_EXEMPT = ("/api/health", "/api/auth/", "/docs", "/openapi.json")


async def gate(request: Request):
    if not enabled():
        return
    path = request.url.path
    if not path.startswith("/api") or any(path.startswith(e) for e in _EXEMPT):
        return
    token = request.headers.get("X-Auth-Token", "")
    if token not in _TOKENS:
        raise HTTPException(401, "authentication required")
