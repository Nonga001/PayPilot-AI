from typing import Any, Protocol

# Every field is always present. Empty string means "not stated in the message".
PAYMENT_FIELDS = ("amount", "currency", "recipient", "recipient_email", "description", "invoice_number", "confidence")


class AIProvider(Protocol):
    name: str
    model: str

    async def extract_payment(self, message: str) -> dict[str, Any]:
        ...
