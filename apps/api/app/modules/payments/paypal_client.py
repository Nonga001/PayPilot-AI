import os
import base64
import requests
from typing import Any
from dotenv import load_dotenv

load_dotenv()

class PayPalClient:
    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        self.base_url = os.getenv("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com")

        if not self.client_id or not self.client_secret:
            raise ValueError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")

    # ------------------------------------------------------------------
    # OAuth 2.0 client credentials
    # ------------------------------------------------------------------
    def _get_access_token(self) -> str:
        """
        Exchange client ID + secret for an OAuth 2.0 access token.
        Endpoint: POST /v1/oauth2/token
        """
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        response = requests.post(
            f"{self.base_url}/v1/oauth2/token",
            headers=headers,
            data=data,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        token = self._get_access_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    # ------------------------------------------------------------------
    # Create order
    # ------------------------------------------------------------------
    def create_order(
        self,
        amount: str,
        currency: str = "USD",
        description: str = "PayPilot AI payment",
        return_url: str = "http://localhost:3000/payment/success",
        cancel_url: str = "http://localhost:3000/payment/cancel",
    ) -> dict[str, Any]:
        """
        Create a PayPal order.
        Endpoint: POST /v2/checkout/orders
        """
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": amount,
                    },
                    "description": description,
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                        "brand_name": "PayPilot AI",
                        "locale": "en-US",
                        "landing_page": "LOGIN",
                        "shipping_preference": "NO_SHIPPING",
                        "user_action": "PAY_NOW",
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        }

        response = requests.post(
            f"{self.base_url}/v2/checkout/orders",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Capture order
    # ------------------------------------------------------------------
    def capture_order(self, order_id: str) -> dict[str, Any]:
        """
        Capture an approved PayPal order.
        Endpoint: POST /v2/checkout/orders/{order_id}/capture
        """
        response = requests.post(
            f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
            headers=self._headers(),
            json={},
        )
        response.raise_for_status()
        return response.json()