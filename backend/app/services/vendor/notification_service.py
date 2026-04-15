"""
services/vendor/notification_service.py

Sends coupon notification emails via SMTP (Gmail free tier / any SMTP).

Config keys expected in .env / Settings:
  SMTP_HOST        e.g. smtp.gmail.com
  SMTP_PORT        e.g. 587
  SMTP_USERNAME    sender Gmail address
  SMTP_PASSWORD    Gmail App Password (not account password)
  SMTP_FROM_NAME   Display name, e.g. "FlowPriceAI Deals"

Uses Python's built-in smtplib with STARTTLS — no paid service required.
All I/O is run in a thread-pool executor so the async event loop is not blocked.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial

from app.schemas.vendor import NotifyRequest, NotifyResponse

logger = logging.getLogger(__name__)

# ── Lazy import settings to avoid circular import at module level ─────────────
def _get_smtp_settings():
    from app.core.config import settings
    return settings


_DEFAULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; background:#f9f9f9; padding:20px;">
  <div style="max-width:480px;margin:auto;background:#fff;border-radius:8px;padding:32px;">
    <h2 style="color:#2d2d2d;">🎉 You have a special offer!</h2>
    <p style="color:#555;">{message}</p>
    <div style="text-align:center;margin:24px 0;">
      <span style="font-size:28px;font-weight:bold;letter-spacing:4px;
                   background:#f0f0f0;padding:12px 24px;border-radius:6px;">
        {coupon_code}
      </span>
    </div>
    <p style="color:#888;font-size:12px;">
      Use this code at checkout. Limited time offer — don't miss out!
    </p>
  </div>
</body>
</html>
"""


def _send_sync(
    host: str,
    port: int,
    username: str,
    password: str,
    from_name: str,
    to_email: str,
    subject: str,
    html_body: str,
) -> None:
    """
    Synchronous SMTP send — called in a thread-pool executor.
    Uses STARTTLS (port 587). Raises smtplib.SMTPException on failure.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{username}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.ehlo()
        server.starttls()
        server.login(username, password)
        server.sendmail(username, to_email, msg.as_string())


class NotificationService:
    async def send_coupon_email(self, body: NotifyRequest) -> NotifyResponse:
        settings = _get_smtp_settings()

        # Gracefully handle missing SMTP config in dev
        smtp_host = getattr(settings, "SMTP_HOST", None)
        smtp_port = getattr(settings, "SMTP_PORT", 587)
        smtp_username = getattr(settings, "SMTP_USERNAME", None)
        smtp_password = getattr(settings, "SMTP_PASSWORD", None)
        smtp_from_name = getattr(settings, "SMTP_FROM_NAME", settings.APP_NAME)

        if not all([smtp_host, smtp_username, smtp_password]):
            logger.warning(
                "SMTP not configured — skipping email to %s", body.user_email
            )
            return NotifyResponse(
                sent=False,
                recipient=body.user_email,
                coupon_code=body.coupon_code,
                message="SMTP not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD in .env",
            )

        message_text = body.message or (
            f"Here is your exclusive coupon code from {smtp_from_name}. "
            "Apply it at checkout to save instantly!"
        )
        html_body = _DEFAULT_TEMPLATE.format(
            message=message_text,
            coupon_code=body.coupon_code,
        )

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                partial(
                    _send_sync,
                    smtp_host,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    smtp_from_name,
                    body.user_email,
                    body.subject,
                    html_body,
                ),
            )
            logger.info(
                "Coupon email sent → %s (code=%s)", body.user_email, body.coupon_code
            )
            return NotifyResponse(
                sent=True,
                recipient=body.user_email,
                coupon_code=body.coupon_code,
                message="Email sent successfully",
            )
        except Exception as exc:
            logger.error(
                "Failed to send coupon email to %s: %s", body.user_email, exc
            )
            return NotifyResponse(
                sent=False,
                recipient=body.user_email,
                coupon_code=body.coupon_code,
                message=f"Email delivery failed: {exc}",
            )


notification_service = NotificationService()
