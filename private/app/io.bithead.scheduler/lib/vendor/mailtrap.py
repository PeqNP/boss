#
# Scheduler — Mailtrap, over SMTP. The sandbox host is the catalog default.
#

from .protocol import EmailMessage, SendResult
from .smtp import send_smtp


class MailtrapVendor:
    def __init__(self, config: dict):
        self.config = config

    def send(self, message: EmailMessage) -> SendResult:
        return send_smtp(self.config, message)
