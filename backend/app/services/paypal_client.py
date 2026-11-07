import asyncio
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger("paypal_client")

class PayPalClient:
    def __init__(self):
        self.base_url = settings.PAYPAL_BASE_URL.rstrip("/")
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.webhook_id = settings.PAYPAL_WEBHOOK_ID
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @staticmethod
    def format_cents_to_paypal(cents: int) -> str:
        """Convert minor integer units (cents) to PayPal decimal string without float rounding."""
        dollars = abs(cents) // 100
        cents_rem = abs(cents) % 100
        return f"{dollars}.{cents_rem:02d}"

    async def get_access_token(self) -> str:
        """Retrieve cached OAuth client credentials token or refresh safely with asyncio lock."""
        async with self._lock:
            now = datetime.utcnow()
            if self._access_token and self._token_expiry and now < self._token_expiry:
                return self._access_token

            # If sandbox credentials are not set, return mock for local offline testing
            if not self.client_id or not self.client_secret:
                logger.warning("PayPal Client ID or Secret missing. Using simulated sandbox token.")
                self._access_token = "mock_sandbox_access_token"
                self._token_expiry = now + timedelta(hours=1)
                return self._access_token

            auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.base_url}/v1/oauth2/token",
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={"grant_type": "client_credentials"}
                )
                if res.status_code != 200:
                    logger.error(f"PayPal OAuth token refresh failed: {res.text}")
                    raise RuntimeError(f"PayPal authentication failed with status {res.status_code}")

                data = res.json()
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                # Apply 60s safety buffer to avoid token expiration during in-flight requests
                self._token_expiry = now + timedelta(seconds=max(0, expires_in - 60))
                return self._access_token

    async def create_order(
        self,
        intent_id: str,
        amount_cents: int,
        description: str,
        return_url: str = "http://localhost:5173/pay/return",
        cancel_url: str = "http://localhost:5173/pay/cancel"
    ) -> Dict[str, Any]:
        """Create a PayPal Orders v2 CAPTURE order with idempotency."""
        token = await self.get_access_token()
        
        # Offline sandbox fallback if simulated
        if token == "mock_sandbox_access_token":
            return {
                "id": f"ORDER-MOCK-{intent_id[:8]}",
                "status": "CREATED",
                "links": [
                    {"rel": "approve", "href": f"https://www.sandbox.paypal.com/checkoutnow?token=ORDER-MOCK-{intent_id[:8]}"}
                ]
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"intent:{intent_id}:create"
        }

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": intent_id,
                    "custom_id": intent_id,
                    "description": description[:120],
                    "amount": {
                        "currency_code": "USD",
                        "value": self.format_cents_to_paypal(amount_cents)
                    }
                }
            ],
            "application_context": {
                "brand_name": "FireWallet",
                "landing_page": "BILLING",
                "user_action": "PAY_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(f"{self.base_url}/v2/checkout/orders", headers=headers, json=payload)
            if res.status_code not in (200, 201):
                logger.error(f"PayPal Create Order error: {res.text}")
                raise RuntimeError(f"PayPal Create Order failed: {res.text}")
            return res.json()

    async def capture_order(self, order_id: str, intent_id: str) -> Dict[str, Any]:
        """Capture an approved PayPal Order v2."""
        token = await self.get_access_token()

        if token == "mock_sandbox_access_token":
            return {
                "id": order_id,
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [{"id": f"CAPTURE-MOCK-{intent_id[:8]}", "status": "COMPLETED"}]
                        }
                    }
                ]
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"intent:{intent_id}:capture"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(f"{self.base_url}/v2/checkout/orders/{order_id}/capture", headers=headers)
            if res.status_code not in (200, 201):
                logger.error(f"PayPal Capture Order error: {res.text}")
                raise RuntimeError(f"PayPal Capture Order failed: {res.text}")
            return res.json()

    async def create_payout(
        self,
        batch_id: str,
        receiver_email: str,
        amount_cents: int,
        note: str
    ) -> Dict[str, Any]:
        """Dispatch a single Payout item (Vault skim or Bill pay) via PayPal Payouts API."""
        token = await self.get_access_token()

        if token == "mock_sandbox_access_token":
            return {
                "batch_header": {
                    "payout_batch_id": f"PAYOUT-MOCK-{batch_id[:8]}",
                    "batch_status": "SUCCESS"
                }
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "sender_batch_header": {
                "sender_batch_id": batch_id[:30],
                "email_subject": "FireWallet Automated Transfer"
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": self.format_cents_to_paypal(amount_cents),
                        "currency": "USD"
                    },
                    "note": note[:200],
                    "sender_item_id": batch_id[:30],
                    "receiver": receiver_email
                }
            ]
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(f"{self.base_url}/v1/payments/payouts", headers=headers, json=payload)
            if res.status_code not in (200, 201):
                logger.error(f"PayPal Payout error: {res.text}")
                raise RuntimeError(f"PayPal Payout failed: {res.text}")
            return res.json()

    async def verify_webhook_signature(
        self,
        headers: Dict[str, str],
        raw_body: bytes
    ) -> bool:
        """
        Cryptographically verify the webhook transmission with PayPal's
        /v1/notifications/verify-webhook-signature API.
        """
        token = await self.get_access_token()
        if token == "mock_sandbox_access_token":
            logger.info("Mock sandbox mode: Webhook signature verified.")
            return True

        if not self.webhook_id:
            logger.warning("PAYPAL_WEBHOOK_ID not set. Skipping signature verification in development.")
            return True

        try:
            body_json = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return False

        verification_payload = {
            "auth_algo": headers.get("paypal-auth-algo") or headers.get("PAYPAL-AUTH-ALGO"),
            "cert_url": headers.get("paypal-cert-url") or headers.get("PAYPAL-CERT-URL"),
            "transmission_id": headers.get("paypal-transmission-id") or headers.get("PAYPAL-TRANSMISSION-ID"),
            "transmission_sig": headers.get("paypal-transmission-sig") or headers.get("PAYPAL-TRANSMISSION-SIG"),
            "transmission_time": headers.get("paypal-transmission-time") or headers.get("PAYPAL-TRANSMISSION-TIME"),
            "webhook_id": self.webhook_id,
            "webhook_event": body_json
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{self.base_url}/v1/notifications/verify-webhook-signature",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=verification_payload
            )
            if res.status_code == 200:
                data = res.json()
                return data.get("verification_status") == "SUCCESS"
            return False

paypal_client = PayPalClient()
