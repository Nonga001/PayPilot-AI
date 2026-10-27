from fastapi import APIRouter
from pydantic import BaseModel, Field

from .service import extract

router = APIRouter(prefix="/ai", tags=["ai"])


class ParsePaymentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


@router.post("/parse-payment")
async def parse_payment(payload: ParsePaymentRequest):
    """Debug view of the raw extraction. Use /agent/analyze for the real flow."""
    return await extract(payload.message)
