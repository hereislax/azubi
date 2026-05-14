# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für die course-App inkl. Workflow-Integration für Praktikumseinsätze."""
import pytest
from django.apps import apps
from django.contrib.auth.models import User, Group


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("course") is not None


def test_models_importable():
    """Models-Modul lädt ohne ImportError."""
    from course import models  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Workflow-Integration für InternshipAssignment
# ─────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.django_db


def test_internship_assignment_workflow_definition_seeded():
    from workflow.models import WorkflowDefinition
    wd = WorkflowDefinition.objects.get(code='internship_assignment')
    steps = list(wd.steps.order_by('order'))
    assert len(steps) == 1
    assert steps[0].approver_type == 'role'
    assert steps[0].approver_value == 'training_coordinator'
    assert wd.reject_behavior == 'final'


@pytest.fixture
def coord_user(db):
    user = User.objects.create_user(username='coord_ia', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungskoordination')
    user.groups.add(group)
    return user


@pytest.fixture
def office_user(db):
    user = User.objects.create_user(username='office_ia', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsreferat')
    user.groups.add(group)
    return user


@pytest.fixture
def dummy_assignment(db):
    """Stand-in für InternshipAssignment via WorkflowDefinition als Target."""
    from workflow.models import WorkflowDefinition
    return WorkflowDefinition.objects.create(
        code='__test_assignment_target__', name='Assignment-Stub',
    )


class TestInternshipAssignmentWorkflow:

    def test_start_creates_instance_in_progress(self, dummy_assignment, office_user):
        from course.workflow_helpers import start_assignment_workflow
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        start_assignment_workflow(dummy_assignment, initiator=office_user)
        inst = get_instance_for(dummy_assignment)
        assert inst is not None
        assert inst.status == INSTANCE_STATUS_IN_PROGRESS
        assert inst.current_step.approver_value == 'training_coordinator'

    def test_start_is_idempotent(self, dummy_assignment, office_user):
        """Mehrfacher Start liefert nur eine Instanz (keine Duplikate)."""
        from course.workflow_helpers import start_assignment_workflow
        from workflow.models import WorkflowInstance
        from django.contrib.contenttypes.models import ContentType

        start_assignment_workflow(dummy_assignment, initiator=office_user)
        start_assignment_workflow(dummy_assignment, initiator=office_user)

        ct = ContentType.objects.get_for_model(type(dummy_assignment))
        count = WorkflowInstance.objects.filter(
            target_ct=ct, target_id=dummy_assignment.pk,
        ).count()
        assert count == 1

    def test_mirror_approve_finalizes(self, dummy_assignment, office_user, coord_user):
        from course.workflow_helpers import (
            start_assignment_workflow, mirror_assignment_decision,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        start_assignment_workflow(dummy_assignment, initiator=office_user)
        mirror_assignment_decision(dummy_assignment, actor=coord_user,
                                    action='approve', comment='Einheit hat Kapazität')

        inst = get_instance_for(dummy_assignment)
        assert inst.status == INSTANCE_STATUS_APPROVED

    def test_mirror_reject_finalizes(self, dummy_assignment, office_user, coord_user):
        from course.workflow_helpers import (
            start_assignment_workflow, mirror_assignment_decision,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_REJECTED

        start_assignment_workflow(dummy_assignment, initiator=office_user)
        mirror_assignment_decision(dummy_assignment, actor=coord_user,
                                    action='reject', comment='Termin kollidiert')

        inst = get_instance_for(dummy_assignment)
        assert inst.status == INSTANCE_STATUS_REJECTED

    def test_decision_without_prior_workflow_creates_one(
        self, dummy_assignment, office_user, coord_user,
    ):
        """Legacy-Datensatz ohne Workflow-Instanz: Mirror legt sie nachträglich an."""
        from course.workflow_helpers import mirror_assignment_decision
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        mirror_assignment_decision(dummy_assignment, actor=coord_user,
                                    action='approve')
        inst = get_instance_for(dummy_assignment)
        assert inst is not None
        assert inst.status == INSTANCE_STATUS_APPROVED


# ─────────────────────────────────────────────────────────────────────────────
# AssignmentChangeRequest mit Conditional-Routing
# ─────────────────────────────────────────────────────────────────────────────


def test_change_request_workflow_definition_seeded():
    from workflow.models import WorkflowDefinition
    wd = WorkflowDefinition.objects.get(code='assignment_change_request')
    assert wd.pre_condition == 'target.requires_approval'
    assert wd.reject_behavior == 'final'
    steps = list(wd.steps.order_by('order'))
    assert len(steps) == 1
    assert steps[0].approver_value == 'training_director'


@pytest.fixture
def director_user(db):
    user = User.objects.create_user(username='leitung_cr', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsleitung')
    user.groups.add(group)
    return user


@pytest.fixture
def change_request_factory(db):
    """Erzeugt einen minimal-vollständigen AssignmentChangeRequest."""
    from datetime import date, timedelta
    from course.models import (
        Course, ScheduleBlock, InternshipAssignment, AssignmentChangeRequest,
    )
    from organisation.models import OrganisationalUnit
    from student.models import Student

    def _make(change_type='split', start_in_days=30):
        course = Course.objects.create(
            title=f'Kurs-{change_type}-{start_in_days}',
            start_date=date(2026, 1, 1), end_date=date(2027, 12, 31),
        )
        block = ScheduleBlock.objects.create(
            course=course, name='Block',
            start_date=date(2026, 1, 1), end_date=date(2027, 12, 31),
            block_type='internship',
        )
        student = Student.objects.create(
            first_name='Test', last_name='NK',
            date_of_birth=date(2000, 1, 1), place_of_birth='Berlin',
            course=course,
        )
        unit = OrganisationalUnit.objects.create(name=f'Einheit-{change_type}-{start_in_days}')
        start = date.today() + timedelta(days=start_in_days)
        assignment = InternshipAssignment.objects.create(
            schedule_block=block, student=student, unit=unit,
            start_date=start, end_date=start + timedelta(days=10),
        )
        return AssignmentChangeRequest.objects.create(
            assignment=assignment, change_type=change_type, payload={},
        )

    return _make


class TestAssignmentChangeRequestWorkflow:

    def test_split_requires_approval(self, change_request_factory, director_user):
        """Splitten ist ein zustimmungspflichtiger Typ → Workflow wartet auf Leitung."""
        from course.workflow_helpers import start_change_request_workflow
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_IN_PROGRESS

        cr = change_request_factory(change_type='split')
        start_change_request_workflow(cr, initiator=director_user)
        inst = get_instance_for(cr)
        assert inst.status == INSTANCE_STATUS_IN_PROGRESS
        assert inst.current_step.approver_value == 'training_director'

    def test_instructor_change_auto_approves_via_pre_condition(
        self, change_request_factory, director_user,
    ):
        """Praxistutor-Wechsel ist nicht zustimmungspflichtig → Auto-Approve."""
        from course.workflow_helpers import start_change_request_workflow
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        cr = change_request_factory(change_type='instructor')
        start_change_request_workflow(cr, initiator=director_user)
        inst = get_instance_for(cr)
        assert inst.status == INSTANCE_STATUS_APPROVED

    def test_director_approve_finalizes(self, change_request_factory, director_user):
        from course.workflow_helpers import (
            start_change_request_workflow, mirror_change_request_decision,
        )
        from workflow.engine import get_instance_for
        from workflow.models import INSTANCE_STATUS_APPROVED

        cr = change_request_factory(change_type='shift')
        start_change_request_workflow(cr, initiator=director_user)
        mirror_change_request_decision(cr, actor=director_user, action='approve',
                                        comment='ok')
        inst = get_instance_for(cr)
        assert inst.status == INSTANCE_STATUS_APPROVED

    def test_short_notice_property(self, change_request_factory):
        """``is_short_notice`` ist True bei < 14 Tagen, sonst False."""
        cr_near = change_request_factory(change_type='shift', start_in_days=7)
        cr_far  = change_request_factory(change_type='shift', start_in_days=60)
        assert cr_near.is_short_notice is True
        assert cr_far.is_short_notice is False
