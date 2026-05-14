# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für die assessment-App inkl. Workflow-Integration (Token + Info-Step)."""
import pytest
from django.apps import apps
from django.contrib.auth.models import User, Group


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("assessment") is not None


def test_models_importable():
    """Models-Modul lädt ohne ImportError."""
    from assessment import models  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Workflow-Engine-Integration für assessment_confirm
# ─────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.django_db


def test_assessment_workflow_definition_seeded():
    """Daten-Migration hat den Workflow korrekt angelegt."""
    from workflow.models import WorkflowDefinition
    wd = WorkflowDefinition.objects.get(code='assessment_confirm')
    steps = list(wd.steps.order_by('order'))
    assert len(steps) == 3
    assert steps[0].approver_type == 'external_token'
    assert steps[1].approver_type == 'info'
    assert steps[1].approver_value == 'training_coordinator'
    assert steps[2].approver_type == 'role'
    assert steps[2].approver_value == 'training_office'


@pytest.fixture
def coord_user(db):
    user = User.objects.create_user(username='coord_t', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungskoordination')
    user.groups.add(group)
    return user


@pytest.fixture
def office_user(db):
    user = User.objects.create_user(username='office_t', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsreferat')
    user.groups.add(group)
    return user


@pytest.fixture
def dummy_target(db):
    """Beliebiges DB-Objekt als Workflow-Ziel.

    Workflow-Engine arbeitet über GenericForeignKey, daher genügt ein
    beliebiges Modell — wir verwenden hier eine zweite ``WorkflowDefinition``
    als Stand-in, statt eine komplexe Assessment-Kette aufzubauen.
    """
    from workflow.models import WorkflowDefinition
    return WorkflowDefinition.objects.create(
        code='__test_assessment_target__', name='Stub',
    )


class TestAssessmentWorkflowStages:

    def test_token_submit_advances_to_info_step(self, dummy_target, coord_user):
        from workflow.engine import start_workflow, perform_action, get_instance_for
        from workflow.models import (
            INSTANCE_STATUS_IN_PROGRESS, APPROVER_INFO, ACTION_APPROVE,
        )

        instance = start_workflow('assessment_confirm', target=dummy_target)
        # Stufe 1: Praxistutor via Token (actor=None erlaubt)
        perform_action(instance, actor=None, actor_name='Praxistutor Müller',
                       action=ACTION_APPROVE,
                       comment='Beurteilung über Token-Link eingereicht.')
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        assert instance.current_step.approver_type == APPROVER_INFO
        assert instance.current_step.approver_value == 'training_coordinator'

    def test_coord_acknowledge_advances_to_office_step(self, dummy_target, coord_user):
        from workflow.engine import start_workflow, perform_action, get_instance_for
        from workflow.models import (
            INSTANCE_STATUS_IN_PROGRESS, ACTION_APPROVE, ACTION_ACKNOWLEDGE,
        )

        instance = start_workflow('assessment_confirm', target=dummy_target)
        perform_action(instance, actor=None, actor_name='Praxistutor',
                       action=ACTION_APPROVE)
        instance.refresh_from_db()
        perform_action(instance, actor=coord_user, action=ACTION_ACKNOWLEDGE,
                       comment='Zur Kenntnis genommen.')
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        assert instance.current_step.approver_value == 'training_office'

    def test_full_three_stage_flow(self, dummy_target, coord_user, office_user):
        from workflow.engine import start_workflow, perform_action
        from workflow.models import (
            INSTANCE_STATUS_APPROVED, ACTION_APPROVE, ACTION_ACKNOWLEDGE,
        )

        instance = start_workflow('assessment_confirm', target=dummy_target)
        perform_action(instance, actor=None, actor_name='Praxistutor',
                       action=ACTION_APPROVE)
        instance.refresh_from_db()
        perform_action(instance, actor=coord_user, action=ACTION_ACKNOWLEDGE)
        instance.refresh_from_db()
        perform_action(instance, actor=office_user, action=ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED

    def test_office_can_only_confirm_in_role_step(self, dummy_target, office_user):
        """Office-User darf nicht in Info-Stufe acknowledgen, nur in Role-Stufe approven."""
        from workflow.engine import start_workflow, perform_action, can_act
        from workflow.models import ACTION_APPROVE

        instance = start_workflow('assessment_confirm', target=dummy_target)
        perform_action(instance, actor=None, actor_name='Praxistutor',
                       action=ACTION_APPROVE)
        instance.refresh_from_db()
        # Stufe 2 (info, coord) — Office-User hat keine Berechtigung
        assert can_act(instance, office_user) is False


class TestMirrorOfficeConfirmAutoAcknowledges:
    """Wenn Referat bestätigt, während Koordination noch nicht abgezeichnet hat,
    spielt der Mirror die Acknowledge-Aktion implizit ab."""

    def test_implicit_acknowledge_then_approve(self, dummy_target, office_user):
        from workflow.engine import start_workflow, perform_action, get_instance_for
        from workflow.models import (
            INSTANCE_STATUS_APPROVED, ACTION_APPROVE, ACTION_ACKNOWLEDGE,
            WorkflowTransition, APPROVER_INFO,
        )

        instance = start_workflow('assessment_confirm', target=dummy_target)
        perform_action(instance, actor=None, actor_name='Praxistutor',
                       action=ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.current_step.approver_type == APPROVER_INFO

        # Mirror-Logik: implizit acknowledge + approve
        # (analog zu mirror_office_confirm_to_workflow)
        perform_action(instance, actor=office_user, action=ACTION_ACKNOWLEDGE,
                       comment='Implizit durch Bestätigung des Ausbildungsreferats.')
        instance.refresh_from_db()
        perform_action(instance, actor=office_user, action=ACTION_APPROVE)
        instance.refresh_from_db()

        assert instance.status == INSTANCE_STATUS_APPROVED
        # Audit-Log enthält beide Aktionen
        actions = list(
            WorkflowTransition.objects.filter(instance=instance)
            .values_list('action', flat=True)
        )
        assert actions.count(ACTION_ACKNOWLEDGE) == 1
        # 2 Approves: Stufe 1 (Token) und Stufe 3 (Referat)
        assert actions.count(ACTION_APPROVE) == 2
