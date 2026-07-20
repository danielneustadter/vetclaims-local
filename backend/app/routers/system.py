import datetime as dt
import io
import zipfile

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from .. import auth
from ..config import settings

router = APIRouter(prefix="/api", tags=["system"])


class Passphrase(BaseModel):
    passphrase: str


@router.get("/auth/status")
def auth_status():
    return {"enabled": auth.enabled()}


@router.post("/auth/setup")
def auth_setup(body: Passphrase):
    auth.setup(body.passphrase)
    return {"token": auth.login(body.passphrase)}


@router.post("/auth/login")
def auth_login(body: Passphrase):
    return {"token": auth.login(body.passphrase)}


@router.post("/backup")
def backup():
    """Download a ZIP of the entire data directory (DB, uploads, outputs).
    Store it somewhere encrypted — it contains your records."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in settings.data_dir.rglob("*"):
            if path.is_file() and not path.name.endswith(("-wal", "-shm")):
                z.write(path, path.relative_to(settings.data_dir))
    fname = f"vetclaims-backup-{dt.date.today().isoformat()}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})
