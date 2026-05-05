# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='announcements.send_announcement_emails', bind=True, max_retries=3, default_retry_delay=60)
def send_announcement_emails(self, announcement_id):
    """Versendet die E-Mails für eine veröffentlichte Ankündigung via Celery/Redis."""
    from .models import Announcement
    from services.email import send_mail_sync  # bereits im Worker → direkt senden

    try:
        announcement = Announcement.objects.get(pk=announcement_id)
    except Announcement.DoesNotExist:
        logger.warning('Ankündigung %s nicht gefunden, Task wird abgebrochen.', announcement_id)
        return

    subject   = f'[Ankündigung] {announcement.title}'
    body_text = announcement.body

    attachments = []
    for att in announcement.attachments.all():
        try:
            attachments.append((att.filename, att.file.read(), 'application/octet-stream'))
        except Exception:
            logger.warning('Anhang %s konnte nicht gelesen werden.', att.filename)

    target_emails = announcement.get_target_emails()
    sent = 0
    for _name, email in target_emails:
        try:
            send_mail_sync(
                subject=subject,
                body_text=body_text,
                recipient_list=[email],
                attachments=attachments,
            )
            sent += 1
        except Exception as exc:
            logger.exception('Fehler beim Versenden an %s', email)
            raise self.retry(exc=exc)

    logger.info('Ankündigung %s: %d E-Mails versendet.', announcement_id, sent)
    return sent
