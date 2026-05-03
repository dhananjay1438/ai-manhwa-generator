from __future__ import annotations

import resend

from config import settings
from logger import logger


class NotificationError(RuntimeError):
    pass


class EmailNotifier:
    def __init__(self) -> None:
        self.api_key = settings.resend_api_key
        self.sender = settings.notification_email_from
        self.recipient = settings.notification_email_to

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.sender and self.recipient)

    def send(self, subject: str, text: str) -> None:
        if not self.enabled:
            logger.error(
                "Email notification skipped. Set RESEND_API_KEY, "
                "NOTIFICATION_EMAIL_FROM, and NOTIFICATION_EMAIL_TO."
            )
            return

        resend.api_key = self.api_key
        params: resend.Emails.SendParams = {
            "from": self.sender,
            "to": [self.recipient],
            "subject": subject,
            "text": text,
        }

        try:
            resend.Emails.send(params)
        except Exception as exc:
            raise NotificationError(f"Resend email send failed: {exc}") from exc
