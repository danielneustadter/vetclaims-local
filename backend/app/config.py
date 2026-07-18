from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    data_dir: Path = PROJECT_ROOT / "data"
    ollama_url: str = "http://localhost:11434"
    model_primary: str = "mistral-small:22b"
    model_fast: str = "qwen3:4b"
    model_embed: str = "nomic-embed-text"
    llm_timeout_s: float = 600.0

    model_config = {"env_prefix": "VETCLAIMS_", "env_file": str(PROJECT_ROOT / ".env")}

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vetclaims.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"


settings = Settings()
for d in (settings.data_dir, settings.uploads_dir, settings.output_dir):
    d.mkdir(parents=True, exist_ok=True)
