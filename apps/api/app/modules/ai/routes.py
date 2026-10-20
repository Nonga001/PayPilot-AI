from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .groq_provider import GroqProvider

router = APIRouter(prefix="/ai", tags=["ai"])


class ParsePaymentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


@router.post("/parse-payment")
async def parse_payment(payload: ParsePaymentRequest):
    """
    Take a natural language payment request and return structured JSON.
    """
    try:
        provider = GroqProvider()
        result = await provider.extract_payment(payload.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI extraction failed: {str(e)}")