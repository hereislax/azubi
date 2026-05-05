# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Manuelle Audit-Log-Einträge für Aktionen, die nicht über Model-Signals laufen.

Beispiele: Token-Submits via öffentlicher Endpunkte, Datei-Downloads,
manuelle Bestätigungen ohne Modelländerung.
"""
import logging

from .models import AuditLogEntry
from .registry import _student_id_from_instance

logger = logging.getLogger(__name__)


def log_event(action, instance, user=None, changes=None, student_id=None):
    """Schreibt einen ``AuditLogEntry`` für eine nicht-signalbasierte Aktion.

    ``user`` darf ``None`` sein (z.B. anonymer Token-Submit).
    ``student_id`` wird sonst aus ``instance`` abgeleitet.
    """
    sender = type(instance)
    try:
        AuditLogEntry.objects.create(
            user=user,
            action=action,
            app_label=sender._meta.app_label,
            model_name=sender._meta.model_name,
            model_verbose_name=str(sender._meta.verbose_name),
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes=changes or {},
            student_id=student_id or _student_id_from_instance(instance),
        )
    except Exception:
        logger.exception(
            "auditlog: failed to write manual log entry for %s %s",
            sender, instance.pk,
        )