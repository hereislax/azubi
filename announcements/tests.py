# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für die announcements-App inkl. Workflow-Integration."""
import pytest
from django.apps import apps
from django.contrib.auth.models import User, Group


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("announcements") is not None


def test_models_importable():
    """Models-Modul lädt ohne ImportError."""
    from announcements import models  # noqa: F401


def test_completion_hook_registered():
    """AppConfig.ready() hat den Completion-Hook beim Workflow registriert."""
    from workflow.engine import _COMPLETION_HOOKS
    assert 'announcement_publish' in _COMPLETION_HOOKS
    assert len(_COMPLETION_HOOKS['announcement_publish']) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Workflow-Integration: Publish-Pfad
# ─────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.django_db


@pytest.fixture
def director_user(db):
    user = User.objects.create_user(username='dir', password='x',
                                    first_name='Dir', last_name='Ektor')
    group, _ = Group.objects.get_or_create(name='ausbildungsleitung')
    user.groups.add(group)
    return user


@pytest.fixture
def office_user(db):
    """Sachbearbeiter:in mit Veröffentlichungs-Recht, aber Freigabe-pflichtig."""
    user = User.objects.create_user(username='office', password='x',
                                    first_name='Sach', last_name='Bearbeit')
    group, _ = Group.objects.get_or_create(name='ausbildungsreferat')
    user.groups.add(group)
    from services.models import AusbildungsreferatProfile, UserProfile
    AusbildungsreferatProfile.objects.create(user=user, can_manage_announcements=True)
    UserProfile.objects.filter(user=user).update(announcement_requires_approval=True)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def trusted_office_user(db):
    """Sachbearbeiter:in OHNE Freigabe-Pflicht."""
    user = User.objects.create_user(username='trusted', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsreferat')
    user.groups.add(group)
    from services.models import AusbildungsreferatProfile, UserProfile
    AusbildungsreferatProfile.objects.create(user=user, can_manage_announcements=True)
    UserProfile.objects.filter(user=user).update(announcement_requires_approval=False)
    # Frische User-Instanz holen, damit OneToOne-Reverse-Cache leer ist
    return User.objects.get(pk=user.pk)


@pytest.fixture
def draft_announcement(db, office_user):
    from announcements.models import Announcement, TARGET_ALL_STUDENTS, STATUS_DRAFT
    return Announcement.objects.create(
        title='Test', body='Inhalt',
        sender=office_user,
        target_type=TARGET_ALL_STUDENTS,
        status=STATUS_DRAFT,
        send_email=False,
    )


class TestPublishOrRequestApproval:

    def test_director_publishes_directly(self, db, director_user, draft_announcement):
        from announcements.views import _publish_or_request_approval
        from announcements.models import STATUS_PUBLISHED
        published, msg = _publish_or_request_approval(draft_announcement, director_user)
        draft_announcement.refresh_from_db()
        assert published is True
        assert draft_announcement.status == STATUS_PUBLISHED

    def test_office_user_triggers_approval(self, db, office_user, draft_announcement):
        from announcements.views import _publish_or_request_approval
        from announcements.models import STATUS_DRAFT
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        published, msg = _publish_or_request_approval(draft_announcement, office_user)
        draft_announcement.refresh_from_db()
        assert published is False
        assert draft_announcement.status == STATUS_DRAFT
        instance = get_instance_for(draft_announcement)
        assert instance is not None
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS

    def test_trusted_office_user_publishes_via_pre_condition(self, db, trusted_office_user):
        """Pre-Condition unerfüllt → Auto-Approve, Hook veröffentlicht."""
        from announcements.models import (
            Announcement, TARGET_ALL_STUDENTS, STATUS_DRAFT, STATUS_PUBLISHED,
        )
        from announcements.views import _publish_or_request_approval
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        ann = Announcement.objects.create(
            title='Trust', body='ok', sender=trusted_office_user,
            target_type=TARGET_ALL_STUDENTS, status=STATUS_DRAFT, send_email=False,
        )
        published, msg = _publish_or_request_approval(ann, trusted_office_user)
        # Workflow muss auto-approved sein
        instance = get_instance_for(ann)
        assert instance.status == INSTANCE_STATUS_APPROVED, \
            f'Instance status: {instance.status}, profile.flag={trusted_office_user.profile.announcement_requires_approval}'
        ann.refresh_from_db()
        assert ann.status == STATUS_PUBLISHED
        assert published is True

    def test_approve_via_workflow_publishes(self, db, office_user, director_user, draft_announcement):
        """Director approved → Hook veröffentlicht die Ankündigung."""
        from announcements.views import _publish_or_request_approval
        from announcements.models import STATUS_PUBLISHED
        from workflow.engine import get_instance_for, perform_action
        from workflow.models import ACTION_APPROVE

        _publish_or_request_approval(draft_announcement, office_user)
        instance = get_instance_for(draft_announcement)
        perform_action(instance, actor=director_user, action=ACTION_APPROVE,
                       comment='ok')
        draft_announcement.refresh_from_db()
        assert draft_announcement.status == STATUS_PUBLISHED
