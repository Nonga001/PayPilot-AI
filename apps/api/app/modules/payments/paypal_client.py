"""PayPal Orders v2 client: cached OAuth token, pooled connections, idempotency keys."""
import threading
import time
from typing import Any

import requests

from app.core import config


class PayPalError(Exception):
    def __init__(self, status: int, name: str, message: str, issue: str | None = None, debug_id: str | None = None):
        self.status, self.name, self.issue, self.debug_id = status, name, issue, debug_id
        super().__init__(message)

    @classmethod
    def from_response(cls, r: requests.Response) -> "PayPalError":
        try:
            body = r.json()
        except ValueError:
            body = {}
        details = body.get("details") or [{}]
        issue = details[0].get("issue")
        desc = details[0].get("description")
        name = body.get("name") or body.get("error") or f"HTTP_{r.status_code}"
        msg = desc or body.get("message") or body.get("error_description") or r.text[:200] or name
        return cls(r.status_code, name, msg, issue, body.get("debug_id"))


class PayPalClient:
    def __init__(self) -> None:
        if not config.PAYPAL_CLIENT_ID or not config.PAYPAL_CLIENT_SECRET:
            raise PayPalError(500, "CONFIG", "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set in apps/api/.env")
        self.base = config.PAYPAL_API_BASE
        self.session = requests.Session()
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_expiry - 60:
                return self._token
            r = self.session.post(
                f"{self.base}/v1/oauth2/token",
                auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                timeout=(5, 15),
            )
            if not r.ok:
                raise PayPalError.from_response(r)
            body = r.json()
            self._token = body["access_token"]
            self._token_expiry = time.time() + int(body.get("expires_in", 3000))
            return self._token

    def _call(self, method: str, path: str, json: dict | None = None, request_id: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json",
                   "Prefer": "return=representation"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id  # PayPal de-duplicates retries with the same id
        r = self.session.request(method, f"{self.base}{path}", json=json, headers=headers, timeout=(5, 25))
        if not r.ok:
            raise PayPalError.from_response(r)
        return r.json() if r.content else {}

    def create_order(self, *, amount: str, currency: str, description: str, custom_id: str,
                     payee_email: str | None, return_url: str, cancel_url: str, request_id: str) -> dict[str, Any]:
        unit: dict[str, Any] = {
            "reference_id": custom_id[:256],
            "custom_id": custom_id[:127],
            "description": (description or "PayPilot AI payment")[:127],
            "amount": {"currency_code": currency, "value": amount},
        }
        if payee_email:
            unit["payee"] = {"email_address": payee_email}
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [unit],
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
        return self._call("POST", "/v2/checkout/orders", payload, request_id=request_id)

    def capture_order(self, order_id: str) -> dict[str, Any]:
        return self._call("POST", f"/v2/checkout/orders/{order_id}/capture", {}, request_id=f"capture-{order_id}")

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v2/checkout/orders/{order_id}")

    # ---------------------------------------------------------------- Payouts
    def create_payout(self, *, batch_id: str, item_id: str, amount: str, currency: str,
                      receiver_email: str, note: str) -> dict[str, Any]:
        """Send money from the business balance to a PayPal email (supplier payment)."""
        payload = {
            "sender_batch_header": {
                "sender_batch_id": batch_id[:127],
                "email_subject": "You have a payment from PayPilot",
                "email_message": (note or "Payment sent with PayPilot")[:1000],
            },
            "items": [{
                "recipient_type": "EMAIL",
                "receiver": receiver_email,
                "amount": {"value": amount, "currency": currency},
                "note": (note or "Payment sent with PayPilot")[:4000],
                "sender_item_id": item_id[:63],
                "notification_language": "en-US",
            }],
        }
        return self._call("POST", "/v1/payments/payouts", payload, request_id=batch_id)

    def get_payout(self, payout_batch_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v1/payments/payouts/{payout_batch_id}")

    # -------------------------------------------------------------- Invoicing
    def search_invoices(self, *, recipient_email: str | None = None, invoice_number: str | None = None,
                        status: list[str] | None = None, page_size: int = 10) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if recipient_email:
            body["recipient_email"] = recipient_email
        if invoice_number:
            body["invoice_number"] = invoice_number
        if status:
            body["status"] = status
        return self._call("POST", f"/v2/invoicing/search-invoices?page_size={page_size}&total_required=true", body)

    def create_invoice(self, *, amount: str, currency: str, recipient_name: str, recipient_email: str,
                       description: str, reference: str, request_id: str) -> dict[str, Any]:
        given, _, surname = (recipient_name or "").strip().partition(" ")
        billing: dict[str, Any] = {"email_address": recipient_email}
        if given:
            billing["name"] = {"given_name": given[:140], **({"surname": surname[:140]} if surname else {})}
        payload = {
            "detail": {
                "currency_code": currency,
                "reference": reference[:120],
                "note": "Thank you for your business.",
                "memo": f"Created by PayPilot ({reference})"[:500],
                "payment_term": {"term_type": "NET_10"},
            },
            "invoicer": {"business_name": config.BUSINESS_NAME[:300]},
            "primary_recipients": [{"billing_info": billing}],
            "items": [{
                "name": (description or "Services")[:200],
                "quantity": "1",
                "unit_amount": {"currency_code": currency, "value": amount},
                "unit_of_measure": "QUANTITY",
            }],
            "configuration": {"allow_tip": False, "tax_inclusive": False},
        }
        return self._call("POST", "/v2/invoicing/invoices", payload, request_id=request_id)

    def send_invoice(self, invoice_id: str) -> dict[str, Any]:
        return self._call("POST", f"/v2/invoicing/invoices/{invoice_id}/send",
                          {"send_to_invoicer": False, "send_to_recipient": True},
                          request_id=f"send-{invoice_id}")

    def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v2/invoicing/invoices/{invoice_id}")


_client: PayPalClient | None = None
_client_lock = threading.Lock()


def paypal() -> PayPalClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = PayPalClient()
        return _client


def approval_link(order: dict[str, Any]) -> str | None:
    for link in order.get("links", []):
        if link.get("rel") in ("payer-action", "approve"):
            return link.get("href")
    return None
