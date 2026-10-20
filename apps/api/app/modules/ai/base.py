from typing import Protocol, Any

class AIProvider(Protocol):
    async def extract_payment(self, message: str) -> dict[str, Any]:
        ...