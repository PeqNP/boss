#
# Scheduler — Twilio, for SMS.
#

import httpx

from .protocol import SendResult, SmsMessage


class TwilioVendor:
    def __init__(self, config: dict):
        self.config = config

    def send(self, message: SmsMessage) -> SendResult:
        sid = str(self.config.get("accountSid") or "").strip()
        token = str(self.config.get("authToken") or "")
        origin = str(self.config.get("fromNumber") or "").strip()
        if not sid or not token or not origin:
            return SendResult(
                sent=False,
                reason="Missing accountSid, authToken, or fromNumber."
            )
        try:
            response = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={"From": origin, "To": message.to, "Body": message.body},
                timeout=10.0
            )
            if response.status_code >= 400:
                return SendResult(sent=False, reason=response.text)
            return SendResult(sent=True, reason="")
        except Exception as error:
            return SendResult(sent=False, reason=str(error))
