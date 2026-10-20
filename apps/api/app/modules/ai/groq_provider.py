import os
import json
from groq import Groq
from .base import AIProvider

class GroqProvider(AIProvider):
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

        self.payment_schema = {
            "type": "object",
            "properties": {
                "amount": {"type": "string", "description": "The payment amount, e.g., '10.00'"},
                "currency": {"type": "string", "description": "The 3-letter currency code, e.g., 'USD'"},
                "recipient": {"type": "string", "description": "The name of the person or entity receiving the payment"},
                "description": {"type": "string", "description": "A brief description of what the payment is for"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"], "description": "The model's confidence in its extraction"}
            },
            "required": ["amount", "currency", "recipient", "description", "confidence"],
            "additionalProperties": False,
        }

    async def extract_payment(self, message: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a payment extraction assistant. Extract the payment details from the user's message and return them as a JSON object."},
                {"role": "user", "content": message}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "payment_extraction",
                    "strict": True,
                    "schema": self.payment_schema
                }
            },
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)