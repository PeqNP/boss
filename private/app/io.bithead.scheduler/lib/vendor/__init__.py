#
# Scheduler — which vendor sends mail, texts, and takes the money.
#
# The catalog is code: SMTP and Mailtrap for email, Twilio for SMS, Stripe
# for payment, and a mock of each in development. `vendor_configs` stores
# the choice and the credentials the user typed, not the list of vendors.
#

import json

from typing import List, Optional

import debug

from ... import db
from ...model import ChannelVendors, PaymentProduct, VendorField, VendorOffer
from ..exception import ValidationError
from .boss_smtp import SmtpVendor
from .mailtrap import MailtrapVendor
from .mock import MockEmailVendor, MockPaymentVendor, MockSmsVendor
from .protocol import (
    EmailMessage, JobCharge, PaymentNotice, SendResult, SmsMessage
)
from .stripe import StripeVendor
from .twilio import TwilioVendor


CHANNELS = ("email", "sms", "payment")


def _field(
    key: str,
    label: str,
    kind: str = "text",
    secret: bool = False,
    default: Optional[str] = None
) -> VendorField:
    return VendorField(
        key=key,
        label=label,
        kind=kind,
        secret=secret,
        default=default
    )


OFFERS = {
    "email": [
        VendorOffer(id="smtp", name="SMTP", fields=[]),
        VendorOffer(
            id="mailtrap",
            name="Mailtrap",
            fields=[
                _field("host", "Host", default="sandbox.smtp.mailtrap.io"),
                _field("port", "Port", kind="number", default="2525"),
                _field("username", "Username"),
                _field("password", "Password", kind="password", secret=True),
                _field("fromEmail", "From email"),
                _field("fromName", "From name")
            ]
        )
    ],
    "sms": [
        VendorOffer(
            id="twilio",
            name="Twilio",
            fields=[
                _field("accountSid", "Account SID"),
                _field("authToken", "Auth token", kind="password", secret=True),
                _field("fromNumber", "From number")
            ]
        )
    ],
    "payment": [
        VendorOffer(
            id="stripe",
            name="Stripe",
            fields=[
                _field(
                    "secretKey",
                    "Secret key",
                    kind="password",
                    secret=True
                ),
                _field("publishableKey", "Publishable key"),
                _field(
                    "webhookSecret",
                    "Webhook secret",
                    kind="password",
                    secret=True
                )
            ]
        )
    ]
}


MOCK_OFFER = VendorOffer(id="mock", name="Mock", fields=[])


ADAPTERS = {
    ("email", "smtp"): SmtpVendor,
    ("email", "mailtrap"): MailtrapVendor,
    ("email", "mock"): MockEmailVendor,
    ("sms", "twilio"): TwilioVendor,
    ("sms", "mock"): MockSmsVendor,
    ("payment", "stripe"): StripeVendor,
    ("payment", "mock"): MockPaymentVendor
}


EMAIL_SUBJECT = "Your appointment"


def _offers(channel: str) -> List[VendorOffer]:
    offers = list(OFFERS.get(channel) or [])
    if debug.is_enabled():
        offers.append(MOCK_OFFER)
    return offers


def _known_ids(channel: str) -> set:
    return {offer.id for offer in _offers(channel)}


def _offer(channel: str, vendor_id: str) -> Optional[VendorOffer]:
    for offer in _offers(channel):
        if offer.id == vendor_id:
            return offer
    return None


def _secret_keys(offer: VendorOffer) -> set:
    return {field.key for field in offer.fields if field.secret}


def _row(channel: str) -> Optional["db.VendorConfigRow"]:
    row = db.get_vendor_config(channel)
    if row is None:
        return None
    if row.vendor_name not in _known_ids(channel):
        return None
    return row


def _public_config(offer: VendorOffer, stored: dict) -> dict:
    secrets = _secret_keys(offer)
    return {
        key: value
        for key, value in stored.items()
        if key not in secrets and value not in (None, "")
    }


def _configured_keys(stored: dict) -> List[str]:
    return sorted(
        key for key, value in stored.items()
        if value not in (None, "")
    )


def _channel(channel: str) -> ChannelVendors:
    if channel not in CHANNELS:
        raise ValidationError(f"The platform has no {channel} vendors.")
    row = _row(channel)
    stored = json.loads(row.config_json) if row else {}
    offer = _offer(channel, row.vendor_name) if row else None
    return ChannelVendors(
        channel=channel,
        chosen=row.vendor_name if row else None,
        vendors=_offers(channel),
        config=_public_config(offer, stored) if offer else {},
        configuredKeys=_configured_keys(stored) if offer else []
    )


def get_vendors() -> List[ChannelVendors]:
    """Every channel, and which vendor is chosen for it."""
    return [_channel(name) for name in CHANNELS]


def get_vendor(channel: str) -> ChannelVendors:
    """One channel's catalog, and the choice on it."""
    return _channel(channel)


def set_vendor(
    channel: str,
    vendor_id: Optional[str],
    config: Optional[dict] = None
) -> ChannelVendors:
    """Choose the service one channel goes through.

    `vendor_id` of `None` clears the choice. An empty secret on a re-save
    leaves the stored value: the form never gets the password back, so it
    cannot send it again.
    """
    if channel not in CHANNELS:
        raise ValidationError(f"The platform has no {channel} vendors.")
    if vendor_id is not None and vendor_id not in _known_ids(channel):
        known = ", ".join(sorted(_known_ids(channel)))
        raise ValidationError(
            f"{vendor_id} is not a {channel} vendor. Choose one of: {known}."
        )

    incoming = dict(config or {})
    existing = db.get_vendor_config(channel)
    if (
        vendor_id is not None
        and existing is not None
        and existing.vendor_name == vendor_id
    ):
        stored = json.loads(existing.config_json)
        offer = _offer(channel, vendor_id)
        for key in _secret_keys(offer) if offer else []:
            if not str(incoming.get(key) or ""):
                incoming[key] = stored.get(key, "")

    db.clear_vendor_config(channel)
    if vendor_id is not None:
        db.insert_vendor_config(
            channel,
            vendor_id,
            json.dumps(incoming)
        )
    return _channel(channel)


def channel_chosen(channel: str) -> Optional[str]:
    """The vendor id chosen for this channel, or `None`."""
    row = _row(channel)
    return row.vendor_name if row else None


def payment_connected(business_id: int) -> bool:
    """Whether this business has a connected payment account."""
    if channel_chosen("payment") is None:
        return False
    return bool(db.get_business_stripe_account(business_id))


def _adapter(channel: str):
    row = _row(channel)
    if row is None:
        return None
    cls = ADAPTERS.get((channel, row.vendor_name))
    if cls is None:
        return None
    return cls(json.loads(row.config_json))


def deliver(
    channel: str,
    destination: str,
    body: str,
    subject: str = EMAIL_SUBJECT
) -> SendResult:
    """Send on the chosen vendor, or say why not.

    Never raises. A confirmation that did not go out is not a booking that
    did not happen.
    """
    adapter = _adapter(channel)
    if adapter is None:
        return SendResult(
            sent=False,
            reason=f"No {channel} vendor is chosen."
        )
    if channel == "email":
        return adapter.send(EmailMessage(destination, subject, body))
    if channel == "sms":
        return adapter.send(SmsMessage(destination, body))
    return SendResult(
        sent=False,
        reason=f"{channel} is not a message channel."
    )


def _payment():
    adapter = _adapter("payment")
    if adapter is None:
        raise ValidationError(
            "Choose a payment vendor on Vendors before connecting Stripe."
        )
    return adapter


def connect_url(business_id: int, return_url: str) -> str:
    return _payment().connect_url(business_id, return_url)


def complete_connect(business_id: int, code: str) -> str:
    return _payment().complete_connect(business_id, code)


def list_products(business_id: int) -> List[PaymentProduct]:
    return _payment().products(business_id)


def payment_link(charge: JobCharge) -> str:
    return _payment().payment_link(charge)


def apply_webhook(
    payload: bytes,
    headers: dict
) -> Optional[PaymentNotice]:
    adapter = _adapter("payment")
    if adapter is None:
        return None
    return adapter.apply_webhook(payload, headers)


def charge_for_job(
    business_id: int,
    job_id: int,
    return_url: str
) -> JobCharge:
    """What a card charge for this appointment is for."""
    from ..money import amount_to_charge
    return JobCharge(
        business_id,
        job_id,
        amount_to_charge(job_id),
        "usd",
        return_url
    )


__all__ = [
    "CHANNELS",
    "EMAIL_SUBJECT",
    "EmailMessage",
    "JobCharge",
    "PaymentNotice",
    "SendResult",
    "SmsMessage",
    "apply_webhook",
    "channel_chosen",
    "charge_for_job",
    "complete_connect",
    "connect_url",
    "deliver",
    "get_vendor",
    "get_vendors",
    "list_products",
    "payment_connected",
    "payment_link",
    "set_vendor"
]
