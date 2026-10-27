from fastapi import APIRouter

from .policy import limits_view

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/policy")
def policy():
    """Current limits. Checks themselves run server-side inside /agent/analyze and /payments/create-order."""
    return {"limits": limits_view()}
