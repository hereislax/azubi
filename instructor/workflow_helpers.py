# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Workflow-Engine-Brücke für die Bestätigung von Praxistutoren."""
import logging

logger = logging.getLogger(__name__)


def start_instructor_workflow(instructor, initiator=None):
    """Startet den Bestätigungs-Workflow für einen neu angelegten Praxistutor."""
    try:
        from workflow.engine import start_workflow, get_instance_for, WorkflowError
        if get_instance_for(instructor) is not None:
            return None
        return start_workflow('instructor_confirmation', target=instructor,
                               initiator=initiator)
    except WorkflowError as exc:
        logger.warning('Instructor-Workflow konnte nicht gestartet werden: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Instructor-Workflow-Start: %s', exc)
    return None


def mirror_instructor_action(instructor, *, actor, action, comment=''):
    """Spiegelt eine Aktion (approve/reject/cancel) an die Engine."""
    try:
        from workflow.engine import (
            perform_action, get_instance_for, start_workflow, WorkflowError,
        )
        instance = get_instance_for(instructor)
        if instance is None:
            instance = start_workflow('instructor_confirmation', target=instructor,
                                       initiator=actor)
        if instance and instance.is_active:
            perform_action(instance, actor=actor, action=action, comment=comment)
    except WorkflowError as exc:
        logger.warning('Instructor-Workflow-Mirror fehlgeschlagen (%s): %s',
                       action, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Instructor-Workflow-Mirror: %s', exc)
