#
# Scheduler — development vendors.
#
# Email and SMS keep what would have gone out, which is how a UI test types
# an OTP. Payment pretends Connect and a card charge succeeded, which is how
# a UI test finishes a deposit.
#

import json

from typing import List, Optional

from ... import db
from ...model import PaymentProduct
from ..notify import record_sent
from .protocol import (
    EmailMessage, JobCharge, PaymentNotice, SendResult, SmsMessage
)


class MockEmailVendor:
    def __init__(self, config: dict):
        self.config = config

    def send(self, message: EmailMessage) -> SendResult:
        record_sent("email", message.to, message.body)
        return SendResult(sent=True, reason="")


class MockSmsVendor:
    def __init__(self, config: dict):
        self.config = config

    def send(self, message: SmsMessage) -> SendResult:
        record_sent("sms", message.to, message.body)
        return SendResult(sent=True, reason="")


class MockPaymentVendor:
    def __init__(self, config: dict):
        self.config = config

    def connect_url(self, business_id: int, return_url: str) -> str:
        return (
            f"/api/io.bithead.scheduler/business/{business_id}"
            f"/config/stripe/callback?code=mock"
        )

    def complete_connect(self, business_id: int, code: str) -> str:
        account = f"acct_mock_{business_id}"
        db.set_business_stripe_account(business_id, account)
        return account

    def products(self, business_id: int) -> List[PaymentProduct]:
        return [
            PaymentProduct(
                id="prod_mock_1",
                name="Mock service — Small",
                priceId="price_mock_1",
                unitAmount=5000,
                currency="usd"
            ),
            PaymentProduct(
                id="prod_mock_2",
                name="Mock service — Medium",
                priceId="price_mock_2",
                unitAmount=8000,
                currency="usd"
            )
        ]

    def payment_link(self, charge: JobCharge) -> str:
        return f"/api/io.bithead.scheduler/debug/pay/{charge.jobId}"

    def apply_webhook(
        self,
        payload: bytes,
        headers: dict
    ) -> Optional[PaymentNotice]:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        try:
            job_id = int(data.get("jobId"))
        except (TypeError, ValueError):
            return None
        try:
            amount = float(data.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        return PaymentNotice(
            job_id=job_id,
            amount=amount,
            provider_ref=str(data.get("providerRef") or "mock")
        )
