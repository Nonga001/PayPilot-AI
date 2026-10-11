from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.modules.payments.routes import router as payments_router

load_dotenv()

app = FastAPI(title="PayPilot AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "paypilot-api"}