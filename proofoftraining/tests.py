# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für die proofoftraining-App inkl. Workflow-Integration mit Revisions-Zyklus."""
from datetime import date

import pytest
from django.apps import apps
from django.contrib.auth.models import User, Group


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("proofoftraining") is not None


def test_models_importable():
    """Models-Modul lädt ohne ImportError."""
    from proofoftraining import models  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Workflow-Engine-Integration für TrainingRecord (Revisions-Zyklus)
# ─────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.django_db


@pytest.fixture
def director_user(db):
    user = User.objects.create_user(username='leitung_pot', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsleitung')
    user.groups.add(group)
    return user


@pytest.fixture
def student_with_user(db):
    from django.contrib.auth.models import User as AuthUser
    from course.models import Course
    from student.models import Student

    course = Course.objects.create(
        title='POT-Kurs', start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    auth_user = AuthUser.objects.create_user(username='nk_pot', password='x',
                                              first_name='NK', last_name='Test')
    student = Student.objects.create(
        first_name='NK', last_name='Test', date_of_birth=date(2000, 1, 1),
        place_of_birth='Berlin', course=course, user=auth_user,
    )
    return student, auth_user


@pytest.fixture
def record(db, student_with_user):
    from proofoftraining.models import TrainingRecord
    student, _ = student_with_user
    return TrainingRecord.objects.create(
        student=student, week_start=date(2026, 6, 1), status='draft',
    )


class TestTrainingRecordWorkflow:

    def test_submit_starts_workflow(self, db, record, student_with_user):
        from proofoftraining.views import submit_record_to_workflow
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        _, nk = student_with_user
        submit_record_to_workflow(record, initiator=nk)
        inst = get_instance_for(record)
        assert inst is not None
        assert inst.status == INSTANCE_STATUS_IN_PROGRESS
        assert inst.current_step.approver_value == 'training_director'
        assert inst.revision == 1

    def test_approve_finalizes(self, db, record, student_with_user, director_user):
        from proofoftraining.views import (
            submit_record_to_workflow, mirror_record_to_workflow,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        _, nk = student_with_user
        submit_record_to_workflow(record, initiator=nk)
        mirror_record_to_workflow(record, actor=director_user, action='approve')

        inst = get_instance_for(record)
        assert inst.status == INSTANCE_STATUS_APPROVED

    def test_reject_returns_to_initiator(self, db, record, student_with_user, director_user):
        """Ablehnung setzt current_step=None — der Nachweis liegt beim Antragsteller."""
        from proofoftraining.views import (
            submit_record_to_workflow, mirror_record_to_workflow,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        _, nk = student_with_user
        submit_record_to_workflow(record, initiator=nk)
        mirror_record_to_workflow(record, actor=director_user, action='reject',
                                   comment='Bitte Tag 3 überarbeiten')

        inst = get_instance_for(record)
        assert inst.status == INSTANCE_STATUS_IN_PROGRESS
        assert inst.current_step is None
        assert inst.revision == 1

    def test_resubmit_restarts_chain(self, db, record, student_with_user, director_user):
        """Nach Reject → Resubmit: Revision++, current_step ist wieder Stufe 1."""
        from proofoftraining.views import (
            submit_record_to_workflow, mirror_record_to_workflow,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        _, nk = student_with_user
        submit_record_to_workflow(record, initiator=nk)
        mirror_record_to_workflow(record, actor=director_user, action='reject',
                                   comment='nochmal')

        # NK überarbeitet → erneutes Submit
        submit_record_to_workflow(record, initiator=nk)

        inst = get_instance_for(record)
        assert inst.status == INSTANCE_STATUS_IN_PROGRESS
        assert inst.current_step is not None
        assert inst.current_step.order == 1
        assert inst.revision == 2

    def test_audit_trail_keeps_history_across_revisions(self, db, record, student_with_user, director_user):
        """Alle Transitionen (Submit/Reject/Resubmit) bleiben im Audit-Log erhalten."""
        from proofoftraining.views import (
            submit_record_to_workflow, mirror_record_to_workflow,
        )
        from workflow.engine import get_instance_for
        from workflow.models import (
            WorkflowTransition, ACTION_SUBMIT, ACTION_REJECT, ACTION_RESUBMIT,
        )

        _, nk = student_with_user
        submit_record_to_workflow(record, initiator=nk)
        mirror_record_to_workflow(record, actor=director_user, action='reject',
                                   comment='r1')
        submit_record_to_workflow(record, initiator=nk)
        mirror_record_to_workflow(record, actor=director_user, action='reject',
                                   comment='r2')
        submit_record_to_workflow(record, initiator=nk)

        inst = get_instance_for(record)
        actions = list(
            WorkflowTransition.objects
            .filter(instance=inst)
            .order_by('timestamp')
            .values_list('action', flat=True)
        )
        # submit (initial) + 2x reject + 2x resubmit
        assert actions.count(ACTION_SUBMIT) == 1
        assert actions.count(ACTION_REJECT) == 2
        assert actions.count(ACTION_RESUBMIT) == 2
        assert inst.revision == 3
