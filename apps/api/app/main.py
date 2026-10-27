from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import config, db
from app.modules.agent.routes import router as agent_router
from app.modules.ai.routes import router as ai_router
from app.modules.audit.routes import router as audit_router
from app.modules.payments.routes import router as payments_router
from app.modules.security.routes import router as security_router
from app.modules.transactions.routes import router as tx_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title="PayPilot AI API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted({config.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"}),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(agent_router)
app.include_router(payments_router)
app.include_router(tx_router)
app.include_router(audit_router)
app.include_router(security_router)
app.include_router(ai_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "paypilot-api", "version": app.version}
