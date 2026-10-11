from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .paypal_client import PayPalClient

router = APIRouter(prefix="/payments", tags=["payments"])


class CreateOrderRequest(BaseModel):
    amount: str = Field(..., pattern=r"^\d+(\.\d{1,2})?$")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str = Field(default="PayPilot AI payment", max_length=127)


class CaptureOrderRequest(BaseModel):
    order_id: str = Field(..., min_length=1)


@router.post("/create-order")
def create_order(payload: CreateOrderRequest):
    """
    Create a PayPal sandbox order and return the approval URL.
    """
    try:
        client = PayPalClient()
        order = client.create_order(
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
        )

        # Find the approval link PayPal returned
        approval_url = None
        for link in order.get("links", []):
            if link.get("rel") in ("approve", "payer-action"):
                approval_url = link.get("href")
                break

        return {
            "order_id": order.get("id"),
            "status": order.get("status"),
            "approval_url": approval_url,
            "raw": order,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PayPal create order failed: {str(e)}")


@router.post("/capture-order")
def capture_order(payload: CaptureOrderRequest):
    """
    Capture an approved PayPal sandbox order.
    """
    try:
        client = PayPalClient()
        result = client.capture_order(payload.order_id)
        return {
            "order_id": result.get("id"),
            "status": result.get("status"),
            "raw": result,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PayPal capture failed: {str(e)}")