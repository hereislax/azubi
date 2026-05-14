# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für die instructor-App inkl. Bestätigungs-Workflow."""
import pytest
from django.apps import apps
from django.contrib.auth.models import User, Group


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("instructor") is not None


def test_models_importable():
    """Models-Modul lädt ohne ImportError."""
    from instructor import models  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Workflow-Integration für Instructor-Bestätigung
# ─────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.django_db


def test_instructor_confirmation_workflow_seeded():
    from workflow.models import WorkflowDefinition
    wd = WorkflowDefinition.objects.get(code='instructor_confirmation')
    steps = list(wd.steps.order_by('order'))
    assert len(steps) == 1
    assert steps[0].approver_value == 'training_director'
    assert wd.reject_behavior == 'final'


@pytest.fixture
def director_user(db):
    user = User.objects.create_user(username='leitung_instr', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsleitung')
    user.groups.add(group)
    return user


@pytest.fixture
def instructor(db):
    from instructor.models import Instructor, INSTRUCTOR_STATUS_PENDING
    return Instructor.objects.create(
        first_name='Test', last_name='Tutor', email='t.tutor@example.org',
        status=INSTRUCTOR_STATUS_PENDING,
    )


class TestInstructorConfirmationWorkflow:

    def test_start_creates_in_progress_instance(self, instructor, director_user):
        from instructor.workflow_helpers import start_instructor_workflow
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        start_instructor_workflow(instructor, initiator=director_user)
        inst = get_instance_for(instructor)
        assert inst is not None
        assert inst.status == INSTANCE_STATUS_IN_PROGRESS
        assert inst.current_step.approver_value == 'training_director'

    def test_start_idempotent(self, instructor, director_user):
        """Mehrfacher Aufruf legt nur eine Instanz an."""
        from instructor.workflow_helpers import start_instructor_workflow
        from workflow.models import WorkflowInstance
        from django.contrib.contenttypes.models import ContentType

        start_instructor_workflow(instructor, initiator=director_user)
        start_instructor_workflow(instructor, initiator=director_user)

        ct = ContentType.objects.get_for_model(type(instructor))
        count = WorkflowInstance.objects.filter(
            target_ct=ct, target_id=instructor.pk,
        ).count()
        assert count == 1

    def test_mirror_approve_finalizes(self, instructor, director_user):
        from instructor.workflow_helpers import (
            start_instructor_workflow, mirror_instructor_action,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        start_instructor_workflow(instructor, initiator=director_user)
        mirror_instructor_action(instructor, actor=director_user,
                                  action='approve',
                                  comment='Praxistutor bestätigt.')

        inst = get_instance_for(instructor)
        assert inst.status == INSTANCE_STATUS_APPROVED

    def test_mirror_cancel_on_delete(self, instructor, director_user):
        """Beim Löschen eines Praxistutors wird der Workflow als cancelled markiert."""
        from instructor.workflow_helpers import (
            start_instructor_workflow, mirror_instructor_action,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_CANCELLED

        start_instructor_workflow(instructor, initiator=director_user)
        mirror_instructor_action(instructor, actor=director_user,
                                  action='cancel', comment='gelöscht')

        inst = get_instance_for(instructor)
        assert inst.status == INSTANCE_STATUS_CANCELLED

    def test_mirror_without_prior_start_creates_instance(self, instructor, director_user):
        """Legacy-Datensatz ohne Workflow: Mirror legt ihn nachträglich an."""
        from instructor.workflow_helpers import mirror_instructor_action
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        mirror_instructor_action(instructor, actor=director_user,
                                  action='approve')
        inst = get_instance_for(instructor)
        assert inst is not None
        assert inst.status == INSTANCE_STATUS_APPROVED
