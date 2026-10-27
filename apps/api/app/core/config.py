"""Central settings. Loads apps/api/.env no matter which folder uvicorn is started from."""
import os
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[2]  # .../apps/api
load_dotenv(API_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


PAYPAL_CLIENT_ID = _env("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = _env("PAYPAL_CLIENT_SECRET")
PAYPAL_API_BASE = _env("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com").rstrip("/")

GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "openai/gpt-oss-20b")
AI_TIMEOUT_SECONDS = float(_env("AI_TIMEOUT_SECONDS", "20"))

FRONTEND_URL = _env("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# SQLite file. No database server needed; swap for Postgres later via the store modules.
DB_PATH = Path(_env("PAYPILOT_DB_PATH", str(API_DIR / "data" / "paypilot.db")))
