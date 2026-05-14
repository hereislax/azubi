# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.apps import AppConfig


class AnnouncementsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'announcements'
    verbose_name = 'Ankündigungen'

    def ready(self):
        # Completion-Hook für „announcement_publish" registrieren —
        # bei Approval wird die Ankündigung automatisch veröffentlicht.
        from workflow.engine import register_completion_hook
        from workflow.models import INSTANCE_STATUS_APPROVED
        from .models import Announcement, STATUS_DRAFT

        def _on_announcement_approved(instance, status):
            if status != INSTANCE_STATUS_APPROVED:
                return
            target = instance.target
            if not isinstance(target, Announcement):
                return
            if target.status != STATUS_DRAFT:
                return
            from .views import _do_publish
            _do_publish(target)

        register_completion_hook('announcement_publish', _on_announcement_approved)
