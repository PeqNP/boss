#
# Scheduler — send mail over SMTP.
#
# Mailtrap submits this way. The catalog is what differs: host, port, and
# which secrets the form asks for.
#

import smtplib

from email.mime.text import MIMEText

from .protocol import EmailMessage, SendResult


REQUIRED = ("host", "port", "username", "password", "fromEmail")


def send_smtp(config: dict, message: EmailMessage) -> SendResult:
    """Deliver `message` with the SMTP account in `config`.

    Missing credentials are a state to report, not an exception: the platform
    can choose a vendor before anyone has typed a password.
    """
    missing = [key for key in REQUIRED if not str(config.get(key) or "").strip()]
    if missing:
        return SendResult(
            sent=False,
            reason=f"Missing {', '.join(missing)}."
        )
    try:
        port = int(config["port"])
    except (TypeError, ValueError):
        return SendResult(sent=False, reason="Port is not a number.")

    sender = config["fromEmail"].strip()
    name = str(config.get("fromName") or "").strip()
    origin = f"{name} <{sender}>" if name else sender
    mail = MIMEText(message.body, "plain", "utf-8")
    mail["From"] = origin
    mail["To"] = message.to
    mail["Subject"] = message.subject

    try:
        with smtplib.SMTP(
            str(config["host"]).strip(),
            port,
            timeout=10
        ) as smtp:
            smtp.starttls()
            smtp.login(
                str(config["username"]).strip(),
                str(config["password"])
            )
            smtp.sendmail(sender, [message.to], mail.as_string())
        return SendResult(sent=True, reason="")
    except Exception as error:
        return SendResult(sent=False, reason=str(error))
