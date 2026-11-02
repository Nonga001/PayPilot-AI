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
# Reads photos of invoices. PDFs use GROQ_MODEL on their text instead.
VISION_MODEL = _env("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
# Run the AG Studio assistant on the Insights page (need strong tool calling). The first leads the
# chat; the agents it hands work to use the second. Groq's limits are per model, so two models give
# the assistant twice the tokens per minute on the free plan.
STUDIO_AI_MODELS = [m.strip() for m in _env("GROQ_STUDIO_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",") if m.strip()]
STUDIO_AI_MODEL = STUDIO_AI_MODELS[0]
AI_TIMEOUT_SECONDS = float(_env("AI_TIMEOUT_SECONDS", "20"))

FRONTEND_URL = _env("FRONTEND_URL", "http://localhost:3000").rstrip("/")
# Extra allowed browser origins (comma separated), e.g. your Render web URL.
CORS_ORIGINS = [o.strip().rstrip("/") for o in _env("CORS_ORIGINS").split(",") if o.strip()]

BUSINESS_NAME = _env("BUSINESS_NAME", "PayPilot Demo Business")

# Optional: a PayPal sandbox personal-account email given to the demo payees when the database
# is created, so demo payouts are delivered (instead of "unclaimed") even after a fresh deploy.
DEMO_PAYEE_EMAIL = _env("DEMO_PAYEE_EMAIL").lower()
# Optional: that sandbox account's password, shown in the app so visitors can pay a demo invoice as the
# client. Sandbox only: never put a real PayPal password here.
DEMO_PAYEE_PASSWORD = _env("DEMO_PAYEE_PASSWORD")

# SQLite file. No database server needed; swap for Postgres later via the store modules.
DB_PATH = Path(_env("PAYPILOT_DB_PATH", str(API_DIR / "data" / "paypilot.db")))
