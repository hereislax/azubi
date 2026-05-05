# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""E-Mail-Versand: asynchron via Celery/Redis (Standard) oder synchron."""
import base64


def send_mail(
    subject: str,
    body_text: str,
    recipient_list: list[str],
    body_html: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
):
    """
    Stellt eine E-Mail in die Celery/Redis-Queue.

    Args:
        subject:        Betreffzeile.
        body_text:      Nur-Text-Inhalt.
        recipient_list: Liste der Empfänger-Adressen.
        body_html:      Optionaler HTML-Inhalt.
        attachments:    Optionale Liste von (filename, content_bytes, mimetype).
    """
    from .tasks import send_mail_task

    attachments_b64 = [
        (filename, base64.b64encode(content).decode(), mimetype)
        for filename, content, mimetype in (attachments or [])
    ]
    send_mail_task.delay(
        subject=subject,
        body_text=body_text,
        recipient_list=recipient_list,
        body_html=body_html,
        attachments_b64=attachments_b64 or None,
    )


def send_mail_sync(
    subject: str,
    body_text: str,
    recipient_list: list[str],
    body_html: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
):
    """
    Sendet eine E-Mail direkt (synchron, ohne Celery).
    Nur verwenden innerhalb von Celery-Tasks oder für SMTP-Tests,
    um doppeltes Queuing zu vermeiden.
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    from_email = settings.DEFAULT_FROM_EMAIL
    reply_to   = getattr(settings, 'DEFAULT_REPLY_TO_EMAIL', None)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=recipient_list,
        reply_to=[reply_to] if reply_to else None,
    )
    if body_html:
        msg.attach_alternative(body_html, 'text/html')
    for filename, content, mimetype in (attachments or []):
        msg.attach(filename, content, mimetype)
    msg.send()
