#
# Scheduler — the shapes a vendor speaks, and the protocols that wrap them.
#
# Callers pass these. An adapter builds the vendor's wire format from them.
# Nothing outside this package sends a Stripe-shaped dict or an SMTP message.
#

from typing import Optional, Protocol

from ...model import PaymentProduct


class EmailMessage:
    def __init__(self, to: str, subject: str, body: str):
        self.to = to
        self.subject = subject
        self.body = body


class SmsMessage:
    def __init__(self, to: str, body: str):
        self.to = to
        self.body = body


class SendResult:
    def __init__(self, sent: bool, reason: str = ""):
        self.sent = sent
        self.reason = reason


class JobCharge:
    def __init__(
        self,
        business_id: int,
        job_id: int,
        amount: float,
        currency: str,
        return_url: str
    ):
        self.businessId = business_id
        self.jobId = job_id
        self.amount = amount
        self.currency = currency
        self.returnUrl = return_url


class PaymentNotice:
    def __init__(self, job_id: int, amount: float, provider_ref: str = ""):
        self.jobId = job_id
        self.amount = amount
        self.providerRef = provider_ref


class EmailVendor(Protocol):
    def send(self, message: EmailMessage) -> SendResult: ...


class SmsVendor(Protocol):
    def send(self, message: SmsMessage) -> SendResult: ...


class PaymentVendor(Protocol):
    def connect_url(self, business_id: int, return_url: str) -> str: ...

    def complete_connect(self, business_id: int, code: str) -> str: ...

    def products(self, business_id: int) -> list[PaymentProduct]: ...

    def payment_link(self, charge: JobCharge) -> str: ...

    def apply_webhook(
        self,
        payload: bytes,
        headers: dict
    ) -> Optional[PaymentNotice]: ...
