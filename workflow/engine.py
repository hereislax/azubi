"""Workflow-Engine: Start, Aktionen und Stufen-Übergänge.

Öffentliche API:

- ``start_workflow(code, target, initiator=None)`` → ``WorkflowInstance``
- ``perform_action(instance, actor, action, comment='', actor_name='')`` → ``WorkflowInstance``
- ``get_instance_for(target)`` → aktuelle ``WorkflowInstance`` für ein Zielobjekt
- ``can_act(instance, user)`` → bool
- ``deadline_for(instance)`` → datetime.date oder None
"""
from datetime import timedelta
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .conditions import safe_evaluate
from .approvers import can_approve_step
from .models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStep, WorkflowTransition,
    INSTANCE_STATUS_IN_PROGRESS, INSTANCE_STATUS_APPROVED,
    INSTANCE_STATUS_REJECTED, INSTANCE_STATUS_CANCELLED,
    ACTION_SUBMIT, ACTION_APPROVE, ACTION_REJECT, ACTION_CANCEL,
    ACTION_AUTO_APPROVE, ACTION_AUTO_REJECT, ACTION_ESCALATE, ACTION_REMIND,
    ACTION_ACKNOWLEDGE, ACTION_RESUBMIT,
    APPROVER_INFO,
    REJECT_BEHAVIOR_FINAL, REJECT_BEHAVIOR_TO_FIRST,
    REJECT_BEHAVIOR_TO_INITIATOR,
    TIMEOUT_REMIND, TIMEOUT_ESCALATE_NEXT, TIMEOUT_ESCALATE_TO,
    TIMEOUT_AUTO_APPROVE, TIMEOUT_AUTO_REJECT,
)


class WorkflowError(Exception):
    """Wird geworfen, wenn eine Engine-Operation fachlich unmöglich ist."""


# ── Completion-Hooks ───────────────────────────────────────────────────────
#
# Module können Hooks registrieren, die ausgeführt werden, sobald eine
# Workflow-Instanz abgeschlossen wird. Damit reagiert z.B. ``announcements``
# auf den Final-Approve und veröffentlicht die Bekanntmachung automatisch.
_COMPLETION_HOOKS: dict[str, list] = {}


def register_completion_hook(workflow_code: str, fn):
    """Registriert ``fn(instance, status)`` für einen Workflow-Typ.

    ``status`` ist einer von ``INSTANCE_STATUS_APPROVED/REJECTED/CANCELLED``.
    Mehrere Hooks pro Workflow-Code werden in Registrierungsreihenfolge
    aufgerufen. Fehler in einem Hook beenden die Kette nicht.
    """
    _COMPLETION_HOOKS.setdefault(workflow_code, []).append(fn)


def _run_completion_hooks(instance, status):
    import logging
    log = logging.getLogger(__name__)
    for fn in _COMPLETION_HOOKS.get(instance.definition.code, []):
        try:
            fn(instance, status)
        except Exception:
            log.exception(
                'Completion-Hook für %s fehlgeschlagen', instance.definition.code,
            )


def get_instance_for(target) -> Optional[WorkflowInstance]:
    """Liefert die aktuellste WorkflowInstance für ein Zielobjekt (oder None)."""
    ct = ContentType.objects.get_for_model(target.__class__)
    return WorkflowInstance.objects.filter(
        target_ct=ct, target_id=target.pk,
    ).order_by('-started_at').first()


def can_act(instance: WorkflowInstance, user) -> bool:
    """Prüft, ob ``user`` die aktuelle Stufe entscheiden darf."""
    if not instance.is_active or not instance.current_step:
        return False
    return can_approve_step(instance.current_step, user, instance.target)


def deadline_for(instance: WorkflowInstance):
    """Berechnet das Fristende der aktuellen Stufe (oder None)."""
    step = instance.current_step
    if not step or not step.deadline_days:
        return None
    return instance.current_step_started_at + timedelta(days=step.deadline_days)


# ── Start ──────────────────────────────────────────────────────────────────

@transaction.atomic
def start_workflow(code: str, target, initiator=None) -> WorkflowInstance:
    """Startet einen Workflow für ein Zielobjekt.

    Wenn ``WorkflowDefinition.pre_condition`` gesetzt und beim Auswerten falsch
    ist, wird die Instanz sofort genehmigt (Approval übersprungen). Das ist
    z.B. für Announcements relevant: Wenn die Person kein Approval braucht,
    wird der Workflow trotzdem instanziiert, aber sofort abgeschlossen — der
    Audit-Trail dokumentiert „auto-approved by pre_condition".
    """
    try:
        definition = WorkflowDefinition.objects.get(code=code, is_active=True)
    except WorkflowDefinition.DoesNotExist:
        raise WorkflowError(f'Workflow „{code}" nicht gefunden oder inaktiv.')

    steps = list(definition.active_steps())
    if not steps:
        raise WorkflowError(f'Workflow „{code}" hat keine Stufen definiert.')

    ct = ContentType.objects.get_for_model(target.__class__)

    instance = WorkflowInstance.objects.create(
        definition=definition,
        target_ct=ct,
        target_id=target.pk,
        current_step=steps[0],
        status=INSTANCE_STATUS_IN_PROGRESS,
        initiator=initiator,
    )

    WorkflowTransition.objects.create(
        instance=instance,
        step=None,
        actor=initiator,
        action=ACTION_SUBMIT,
        comment='',
        revision=instance.revision,
    )

    # Pre-Condition prüfen
    if definition.pre_condition:
        passes = safe_evaluate(definition.pre_condition,
                               initiator=initiator, target=target,
                               default=True)
        if not passes:
            # Approval nicht nötig — sofort als auto-genehmigt abschließen
            _finalize(instance, INSTANCE_STATUS_APPROVED,
                      ACTION_AUTO_APPROVE,
                      comment='Pre-Condition nicht erfüllt — automatisch genehmigt.')
            return instance

    # Übersprungs-Bedingung der ersten Stufe prüfen
    _skip_steps_if_needed(instance)

    return instance


# ── Aktionen ───────────────────────────────────────────────────────────────

@transaction.atomic
def perform_action(instance: WorkflowInstance, *,
                   actor=None, action: str,
                   comment: str = '',
                   actor_name: str = '') -> WorkflowInstance:
    """Führt eine Aktion auf einer Workflow-Instanz aus.

    Erlaubte Aktionen: ``approve``, ``reject``, ``cancel``, ``acknowledge``,
    ``resubmit``. System-Aktionen (``escalate``, ``remind``, ``auto_*``)
    werden intern aufgerufen.
    """
    if not instance.is_active and action != ACTION_RESUBMIT:
        raise WorkflowError('Workflow ist nicht mehr aktiv.')

    if action == ACTION_APPROVE:
        return _handle_approve(instance, actor=actor, comment=comment,
                                actor_name=actor_name)

    if action == ACTION_REJECT:
        return _handle_reject(instance, actor=actor, comment=comment,
                              actor_name=actor_name)

    if action == ACTION_CANCEL:
        return _handle_cancel(instance, actor=actor, comment=comment)

    if action == ACTION_ACKNOWLEDGE:
        return _handle_acknowledge(instance, actor=actor, comment=comment)

    if action == ACTION_RESUBMIT:
        return _handle_resubmit(instance, actor=actor, comment=comment)

    raise WorkflowError(f'Unbekannte Aktion: {action}')


def _handle_approve(instance, *, actor, comment, actor_name):
    step = instance.current_step
    if not step:
        raise WorkflowError('Keine aktive Stufe.')

    # Berechtigungs-Check (entfällt bei externem Token — der ruft eine
    # separate Funktion mit pre-authentifiziertem Token auf).
    if actor and not can_approve_step(step, actor, instance.target):
        raise WorkflowError('Keine Berechtigung für diese Stufe.')

    WorkflowTransition.objects.create(
        instance=instance, step=step,
        actor=actor, actor_name=actor_name,
        action=ACTION_APPROVE, comment=comment,
        revision=instance.revision,
    )
    _advance_to_next_step(instance)
    return instance


def _handle_reject(instance, *, actor, comment, actor_name):
    step = instance.current_step
    if not step:
        raise WorkflowError('Keine aktive Stufe.')

    if actor and not can_approve_step(step, actor, instance.target):
        raise WorkflowError('Keine Berechtigung für diese Stufe.')

    WorkflowTransition.objects.create(
        instance=instance, step=step,
        actor=actor, actor_name=actor_name,
        action=ACTION_REJECT, comment=comment,
        revision=instance.revision,
    )

    behavior = instance.definition.reject_behavior

    if behavior == REJECT_BEHAVIOR_TO_FIRST:
        # Zurück auf erste Stufe, History bleibt erhalten
        steps = list(instance.definition.active_steps())
        instance.current_step = steps[0] if steps else None
        instance.current_step_started_at = timezone.now()
        instance.revision += 1
        instance.save(update_fields=['current_step', 'current_step_started_at', 'revision'])
        return instance

    if behavior == REJECT_BEHAVIOR_TO_INITIATOR:
        # Zurück an Antragsteller — Workflow pausiert, bis Resubmit
        # Status bleibt in_progress, current_step = None signalisiert „beim Antragsteller"
        instance.current_step = None
        instance.save(update_fields=['current_step'])
        return instance

    # REJECT_BEHAVIOR_FINAL — Endstand
    _finalize(instance, INSTANCE_STATUS_REJECTED, action=None)
    return instance


def _handle_cancel(instance, *, actor, comment):
    WorkflowTransition.objects.create(
        instance=instance, step=instance.current_step,
        actor=actor, action=ACTION_CANCEL, comment=comment,
        revision=instance.revision,
    )
    _finalize(instance, INSTANCE_STATUS_CANCELLED, action=None)
    return instance


def _handle_acknowledge(instance, *, actor, comment):
    """Info-Step: Aktor zeichnet zur Kenntnis ab, blockiert aber nicht."""
    step = instance.current_step
    if not step or step.approver_type != APPROVER_INFO:
        raise WorkflowError('Aktuelle Stufe ist kein Info-Step.')

    WorkflowTransition.objects.create(
        instance=instance, step=step,
        actor=actor, action=ACTION_ACKNOWLEDGE, comment=comment,
        revision=instance.revision,
    )
    _advance_to_next_step(instance)
    return instance


def _handle_resubmit(instance, *, actor, comment):
    """Antragsteller reicht nach Ablehnung erneut ein."""
    if instance.status != INSTANCE_STATUS_IN_PROGRESS or instance.current_step is not None:
        # Bei „to_initiator" ist current_step=None, status=in_progress
        if not (instance.status == INSTANCE_STATUS_IN_PROGRESS and instance.current_step is None):
            raise WorkflowError('Kein Resubmit möglich in diesem Zustand.')

    steps = list(instance.definition.active_steps())
    if not steps:
        raise WorkflowError('Workflow hat keine Stufen.')

    instance.current_step = steps[0]
    instance.current_step_started_at = timezone.now()
    instance.revision += 1
    instance.save(update_fields=['current_step', 'current_step_started_at', 'revision'])

    WorkflowTransition.objects.create(
        instance=instance, step=instance.current_step,
        actor=actor, action=ACTION_RESUBMIT, comment=comment,
        revision=instance.revision,
    )
    _skip_steps_if_needed(instance)
    return instance


# ── Stufen-Übergang ────────────────────────────────────────────────────────

def _advance_to_next_step(instance: WorkflowInstance):
    """Bewegt die Instanz zur nächsten Stufe oder beendet sie."""
    steps = list(instance.definition.active_steps())
    current_order = instance.current_step.order if instance.current_step else 0
    next_steps = [s for s in steps if s.order > current_order]

    if not next_steps:
        # Letzte Stufe erreicht → genehmigt
        _finalize(instance, INSTANCE_STATUS_APPROVED, action=None)
        return

    instance.current_step = next_steps[0]
    instance.current_step_started_at = timezone.now()
    instance.save(update_fields=['current_step', 'current_step_started_at'])

    _skip_steps_if_needed(instance)


def _skip_steps_if_needed(instance: WorkflowInstance):
    """Prüft skip_condition der aktuellen Stufe und überspringt ggf."""
    step = instance.current_step
    while step and step.skip_condition:
        skip = safe_evaluate(step.skip_condition,
                             initiator=instance.initiator,
                             target=instance.target,
                             default=False)
        if not skip:
            break
        WorkflowTransition.objects.create(
            instance=instance, step=step,
            actor=None, action=ACTION_AUTO_APPROVE,
            comment='Stufe übersprungen (skip_condition erfüllt).',
            revision=instance.revision,
        )
        # Nächste Stufe
        steps = list(instance.definition.active_steps())
        next_steps = [s for s in steps if s.order > step.order]
        if not next_steps:
            _finalize(instance, INSTANCE_STATUS_APPROVED, action=None)
            return
        instance.current_step = next_steps[0]
        instance.current_step_started_at = timezone.now()
        instance.save(update_fields=['current_step', 'current_step_started_at'])
        step = instance.current_step


def _finalize(instance: WorkflowInstance, status: str,
              action: Optional[str], comment: str = ''):
    """Setzt den Endzustand und schreibt ggf. eine letzte Transition."""
    if action:
        WorkflowTransition.objects.create(
            instance=instance, step=instance.current_step,
            actor=None, action=action, comment=comment,
            revision=instance.revision,
        )
    instance.status = status
    instance.current_step = None
    instance.finished_at = timezone.now()
    instance.save(update_fields=['status', 'current_step', 'finished_at'])

    _run_completion_hooks(instance, status)


# ── Timeout-Verarbeitung (vom Celery-Tick aufgerufen) ──────────────────────

@transaction.atomic
def handle_timeout(instance: WorkflowInstance):
    """Wird vom Tick-Task für jede überfällige Instanz aufgerufen.

    Verhält sich gemäß ``step.on_timeout``.
    """
    step = instance.current_step
    if not step or not step.deadline_days:
        return

    on_timeout = step.on_timeout

    if on_timeout == TIMEOUT_REMIND:
        # Reminder werden über separaten Mechanismus geschickt (im Tick).
        return

    if on_timeout == TIMEOUT_ESCALATE_NEXT:
        WorkflowTransition.objects.create(
            instance=instance, step=step, action=ACTION_ESCALATE,
            comment='Frist überschritten — Eskalation auf nächste Stufe.',
            revision=instance.revision,
        )
        _advance_to_next_step(instance)
        return

    if on_timeout == TIMEOUT_ESCALATE_TO:
        # Stufe bleibt, aber der Eskalations-Approver darf entscheiden.
        # Implementierung: temporärer Step mit modifizierter Berechtigung
        # — pragmatisch ohne neuen Step modelliert über approver_value-Override
        # Hier vereinfacht: Transition loggen, Step bleibt offen.
        WorkflowTransition.objects.create(
            instance=instance, step=step, action=ACTION_ESCALATE,
            comment=f'Frist überschritten — eskaliert an „{step.escalate_to_value}".',
            revision=instance.revision,
        )
        # Stufe nicht ändern — der Eskalations-Approver kann jetzt parallel entscheiden.
        # Berechtigungs-Check in can_approve_step könnte erweitert werden, um
        # nach Eskalation auch escalate_to_value zu prüfen.
        return

    if on_timeout == TIMEOUT_AUTO_APPROVE:
        WorkflowTransition.objects.create(
            instance=instance, step=step, action=ACTION_AUTO_APPROVE,
            comment='Frist überschritten — automatisch genehmigt.',
            revision=instance.revision,
        )
        _advance_to_next_step(instance)
        return

    if on_timeout == TIMEOUT_AUTO_REJECT:
        _finalize(instance, INSTANCE_STATUS_REJECTED,
                  action=ACTION_AUTO_REJECT,
                  comment='Frist überschritten — automatisch abgelehnt.')
        return


def mark_reminder_sent(instance: WorkflowInstance, step: WorkflowStep):
    """Wird vom Tick aufgerufen, wenn ein Reminder verschickt wurde."""
    from .models import WorkflowReminder
    WorkflowReminder.objects.get_or_create(
        instance=instance, step=step, revision=instance.revision,
    )
    WorkflowTransition.objects.create(
        instance=instance, step=step, action=ACTION_REMIND,
        comment='Erinnerung versandt.',
        revision=instance.revision,
    )
