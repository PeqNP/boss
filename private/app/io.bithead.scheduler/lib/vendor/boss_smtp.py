#
# Scheduler — BOSS SMTP.
#
# The SMTP catalog choice. Credentials live on `boss.config.smtp`; this
# hands the message to Swift, which already knows how to send.
#

from lib.server import send_smtp

from .protocol import EmailMessage, SendResult


class SmtpVendor:
    def __init__(self, config: dict):
        self.config = config

    def send(self, message: EmailMessage) -> SendResult:
        answer = send_smtp(
            message.to,
            message.body,
            subject=message.subject
        )
        return SendResult(
            sent=bool(answer.get("sent")),
            reason=str(answer.get("reason") or "")
        )
