"""Periodische Workflow-Aufgaben."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .engine import handle_timeout, mark_reminder_sent
from .models import (
    WorkflowInstance, WorkflowReminder,
    INSTANCE_STATUS_IN_PROGRESS,
)

logger = logging.getLogger(__name__)


@shared_task(name='workflow.tick')
def tick_workflows():
    """Geht alle laufenden Instanzen durch, prüft Fristen, sendet Reminder.

    Soll täglich vom Celery-Beat aufgerufen werden. Idempotent: doppelte
    Aufrufe an einem Tag tun nichts, weil Reminder pro
    (instance, step, revision) nur einmal gesendet werden.
    """
    now = timezone.now()
    qs = WorkflowInstance.objects.filter(
        status=INSTANCE_STATUS_IN_PROGRESS,
        current_step__isnull=False,
    ).select_related('current_step', 'definition')

    handled = 0
    reminders = 0
    timeouts = 0

    for instance in qs:
        step = instance.current_step
        if not step.deadline_days:
            continue

        deadline = instance.current_step_started_at + timedelta(days=step.deadline_days)

        if now < deadline:
            # Innerhalb der Frist — ggf. Reminder kurz vor Ablauf
            warn_at = deadline - timedelta(days=1)
            if now >= warn_at:
                already = WorkflowReminder.objects.filter(
                    instance=instance, step=step,
                    revision=instance.revision,
                ).exists()
                if not already:
                    _send_reminder(instance, step)
                    mark_reminder_sent(instance, step)
                    reminders += 1
            continue

        # Frist überschritten
        handle_timeout(instance)
        _send_timeout_notification(instance, step)
        timeouts += 1
        handled += 1

    logger.info(
        'workflow.tick: %d instances checked, %d reminders sent, %d timeouts handled.',
        qs.count(), reminders, timeouts,
    )
    return {'checked': qs.count(), 'reminders': reminders, 'timeouts': timeouts}


def _send_reminder(instance, step):
    """Hookt sich in das vorhandene NotificationTemplate-System ein.

    Modul-spezifische Templates werden über den ``definition.code`` adressiert:
    ``workflow_reminder_<workflow_code>``. Wenn nicht vorhanden, generischer
    Fallback.
    """
    try:
        from services.notifications import send_workflow_reminder
        send_workflow_reminder(instance, step)
    except (ImportError, AttributeError):
        logger.warning('workflow: kein Reminder-Sender registriert (services.notifications.send_workflow_reminder)')


def _send_timeout_notification(instance, step):
    try:
        from services.notifications import send_workflow_timeout
        send_workflow_timeout(instance, step)
    except (ImportError, AttributeError):
        logger.warning('workflow: kein Timeout-Sender registriert')
