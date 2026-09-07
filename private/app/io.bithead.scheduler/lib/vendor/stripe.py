#
# Scheduler — Stripe, for card charges and Connect.
#
# Platform keys live on the Stripe vendor config. Which connected account a
# business uses is `businesses.stripe_account_id`.
#

import hashlib
import hmac
import json
import logging

from typing import List, Optional
from urllib.parse import urlencode

import httpx

from ... import db
from ...model import PaymentProduct
from ..exception import ValidationError
from .protocol import JobCharge, PaymentNotice


STRIPE_API = "https://api.stripe.com/v1"
STRIPE_API_V2 = "https://api.stripe.com/v2"
STRIPE_VERSION = "2026-08-26.dahlia"


class StripeVendor:
    def __init__(self, config: dict):
        self.config = config

    def _secret(self) -> str:
        key = str(self.config.get("secretKey") or "").strip()
        if not key:
            raise ValidationError(
                "Stripe is missing a secret key. Add one on Vendors."
            )
        return key

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._v1(
            httpx.get,
            path,
            params=params or {}
        )

    def _post(self, path: str, data: dict) -> dict:
        return self._v1(httpx.post, path, data=data)

    def _v1(self, method, path: str, **kwargs) -> dict:
        return self._request(
            method,
            f"{STRIPE_API}{path}",
            auth=(self._secret(), ""),
            **kwargs
        )

    def _v2_post(self, path: str, body: dict) -> dict:
        return self._request(
            httpx.post,
            f"{STRIPE_API_V2}{path}",
            headers={
                "Authorization": f"Bearer {self._secret()}",
                "Stripe-Version": STRIPE_VERSION
            },
            json=body
        )

    def _request(self, method, url: str, **kwargs) -> dict:
        response = method(url, timeout=15.0, **kwargs)
        if response.is_error:
            message = _stripe_message(response)
            logging.warning(f"Stripe {url} failed: {message}")
            raise ValidationError(message)
        return response.json()

    def connect_url(self, business_id: int, return_url: str) -> str:
        """Start Connect onboarding for this business."""
        business = db.get_business(business_id)
        body = {
            "dashboard": "full",
            "configuration": {
                "merchant": {
                    "capabilities": {
                        "card_payments": {"requested": True}
                    }
                }
            },
            "defaults": {
                "responsibilities": {
                    "fees_collector": "stripe",
                    "losses_collector": "stripe"
                }
            },
            "identity": {"country": "us"}
        }
        if business and business.name:
            body["display_name"] = business.name
            body["identity"]["business_details"] = {
                "registered_name": business.name
            }
        account = self._v2_post("/core/accounts", body)
        account_id = account.get("id")
        if not account_id:
            raise ValidationError("Stripe did not return an account.")
        link = self._v2_post(
            "/core/account_links",
            {
                "account": account_id,
                "use_case": {
                    "type": "account_onboarding",
                    "account_onboarding": {
                        "configurations": ["merchant"],
                        "collection_options": {"fields": "eventually_due"},
                        "refresh_url": return_url,
                        "return_url": (
                            f"{return_url.split('?')[0]}"
                            f"?{urlencode({'code': account_id})}"
                        )
                    }
                }
            }
        )
        url = link.get("url")
        if not url:
            raise ValidationError("Stripe did not return a Connect URL.")
        return url

    def complete_connect(self, business_id: int, code: str) -> str:
        """Record the connected account Stripe handed back."""
        if not code.strip():
            raise ValidationError("Stripe did not return an account.")
        db.set_business_stripe_account(business_id, code.strip())
        return code.strip()

    def products(self, business_id: int) -> List[PaymentProduct]:
        try:
            payload = self._get(
                "/prices",
                {"active": "true", "limit": 100, "expand[]": "data.product"}
            )
        except Exception as error:
            logging.warning(f"Stripe products failed: {error}")
            raise ValidationError("Could not load Stripe products.")
        products = []
        for price in payload.get("data") or []:
            product = price.get("product") or {}
            if isinstance(product, str):
                name = product
                product_id = product
            else:
                if product.get("active") is False:
                    continue
                name = product.get("name") or price.get("id")
                product_id = product.get("id") or price.get("id")
            products.append(PaymentProduct(
                id=product_id,
                name=name,
                priceId=price.get("id") or "",
                unitAmount=int(price.get("unit_amount") or 0),
                currency=(price.get("currency") or "usd")
            ))
        return products

    def payment_link(self, charge: JobCharge) -> str:
        account = db.get_business_stripe_account(charge.businessId)
        cents = max(1, int(round(charge.amount * 100)))
        data = {
            "line_items[0][price_data][currency]": charge.currency,
            "line_items[0][price_data][product_data][name]": (
                f"Appointment {charge.jobId}"
            ),
            "line_items[0][price_data][unit_amount]": str(cents),
            "line_items[0][quantity]": "1",
            "after_completion[type]": "redirect",
            "after_completion[redirect][url]": charge.returnUrl,
            "metadata[jobId]": str(charge.jobId),
            "metadata[businessId]": str(charge.businessId)
        }
        if account:
            data["transfer_data[destination]"] = account
        try:
            link = self._post("/payment_links", data)
        except Exception as error:
            logging.warning(f"Stripe payment link failed: {error}")
            raise ValidationError("Could not create a payment link.")
        url = link.get("url")
        if not url:
            raise ValidationError("Stripe did not return a payment link.")
        return url

    def apply_webhook(
        self,
        payload: bytes,
        headers: dict
    ) -> Optional[PaymentNotice]:
        secret = str(self.config.get("webhookSecret") or "").strip()
        signature = headers.get("stripe-signature") or headers.get(
            "Stripe-Signature"
        ) or ""
        if secret and not _signed(payload, signature, secret):
            return None
        try:
            event = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        data = (event.get("data") or {}).get("object") or {}
        metadata = data.get("metadata") or {}
        try:
            job_id = int(metadata.get("jobId"))
        except (TypeError, ValueError):
            return None
        amount = (data.get("amount_total") or data.get("amount") or 0) / 100.0
        return PaymentNotice(
            job_id=job_id,
            amount=amount,
            provider_ref=str(data.get("id") or "")
        )


def _stripe_message(response: httpx.Response) -> str:
    """Stripe's own refusal, or a short fallback."""
    try:
        payload = response.json()
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if payload.get("message"):
            return str(payload["message"])
    except Exception:
        pass
    return f"Stripe request failed ({response.status_code})."


def _signed(payload: bytes, header: str, secret: str) -> bool:
    """Stripe's `t=...,v1=...` header, checked as HMAC-SHA256."""
    timestamp = ""
    found = ""
    for part in header.split(","):
        key, _, value = part.partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            found = value
    if not timestamp or not found:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, found)
