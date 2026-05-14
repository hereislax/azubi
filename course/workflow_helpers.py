# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Workflow-Engine-Brücke für Praktikumseinsätze.

Spiegelt die Status-Änderungen am ``InternshipAssignment`` an die generische
Workflow-Engine (``internship_assignment``-Definition). Die Engine läuft
parallel zur klassischen Status-Maschine — Fehler im Mirror unterbrechen die
fachliche Logik nicht.
"""
import logging

logger = logging.getLogger(__name__)


def start_assignment_workflow(assignment, initiator=None):
    """Startet den Workflow für einen neu angelegten Praktikumseinsatz."""
    try:
        from workflow.engine import start_workflow, get_instance_for, WorkflowError
        if get_instance_for(assignment) is not None:
            return None
        return start_workflow('internship_assignment', target=assignment,
                               initiator=initiator)
    except WorkflowError as exc:
        logger.warning('Assignment-Workflow konnte nicht gestartet werden: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Assignment-Workflow-Start: %s', exc)
    return None


def mirror_assignment_decision(assignment, *, actor, action, comment=''):
    """Spiegelt eine Approve/Reject-Entscheidung an die Workflow-Engine.

    ``action`` ist ``'approve'`` oder ``'reject'``.
    """
    try:
        from workflow.engine import (
            perform_action, get_instance_for, start_workflow, WorkflowError,
        )
        instance = get_instance_for(assignment)
        if instance is None:
            initiator = getattr(assignment, 'created_by', None)
            instance = start_workflow('internship_assignment', target=assignment,
                                       initiator=initiator)
        if instance and instance.is_active:
            perform_action(instance, actor=actor, action=action, comment=comment)
    except WorkflowError as exc:
        logger.warning('Assignment-Workflow-Mirror fehlgeschlagen (%s): %s',
                       action, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Assignment-Workflow-Mirror: %s', exc)


# ── Änderungsanträge (AssignmentChangeRequest) ────────────────────────────

def start_change_request_workflow(change_request, initiator=None):
    """Startet den Workflow für einen neuen Änderungsantrag.

    Wenn die Workflow-Definition eine Pre-Condition besitzt
    (``target.requires_approval``), wird der Workflow bei nicht-erfüllter
    Bedingung sofort als „auto_approved" abgeschlossen.
    """
    try:
        from workflow.engine import start_workflow, get_instance_for, WorkflowError
        if get_instance_for(change_request) is not None:
            return None
        return start_workflow('assignment_change_request', target=change_request,
                               initiator=initiator)
    except WorkflowError as exc:
        logger.warning('ChangeRequest-Workflow konnte nicht gestartet werden: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim ChangeRequest-Workflow-Start: %s', exc)
    return None


def mirror_change_request_decision(change_request, *, actor, action, comment=''):
    """Spiegelt eine Approve/Reject-Entscheidung am Änderungsantrag."""
    try:
        from workflow.engine import (
            perform_action, get_instance_for, start_workflow, WorkflowError,
        )
        instance = get_instance_for(change_request)
        if instance is None:
            initiator = getattr(change_request, 'requested_by', None)
            instance = start_workflow('assignment_change_request',
                                       target=change_request, initiator=initiator)
        if instance and instance.is_active:
            perform_action(instance, actor=actor, action=action, comment=comment)
    except WorkflowError as exc:
        logger.warning('ChangeRequest-Workflow-Mirror fehlgeschlagen (%s): %s',
                       action, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim ChangeRequest-Workflow-Mirror: %s', exc)
