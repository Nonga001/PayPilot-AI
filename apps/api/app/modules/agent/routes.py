from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import audit
from app.modules.transactions import store

from .service import analyze

router = APIRouter(prefix="/agent", tags=["agent"])


class AnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


@router.post("/analyze")
async def analyze_route(payload: AnalyzeRequest):
    """One round trip: AI extraction, policy checks, duplicate lookup, explanation, stored proposal."""
    return await analyze(payload.message.strip())


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str):
    p = store.proposal_out(store.get_proposal(proposal_id))
    if not p:
        raise HTTPException(404, "Proposal not found")
    p["audit"] = audit.recent(proposal_id=proposal_id)
    return p
