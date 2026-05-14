# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für die Workflow-Engine.

Geprüft werden:
- Start eines Workflows und Stufen-Übergänge
- Pre-Condition: Auto-Approve, wenn unerfüllt
- Skip-Condition: Stufen werden übersprungen
- Reject-Behavior: final, to_first, to_initiator
- Conditional Evaluator: erlaubte und verbotene Ausdrücke
- Completion-Hooks: Aufruf bei Final-Approve
"""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import User, Group
from django.utils import timezone

from workflow import conditions
from workflow.conditions import ConditionError, evaluate, safe_evaluate
from workflow.engine import (
    WorkflowError,
    start_workflow,
    perform_action,
    get_instance_for,
    register_completion_hook,
    _COMPLETION_HOOKS,
)
from workflow.models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowTransition,
    INSTANCE_STATUS_IN_PROGRESS, INSTANCE_STATUS_APPROVED,
    INSTANCE_STATUS_REJECTED,
    ACTION_APPROVE, ACTION_REJECT, ACTION_RESUBMIT,
    REJECT_BEHAVIOR_FINAL, REJECT_BEHAVIOR_TO_FIRST, REJECT_BEHAVIOR_TO_INITIATOR,
)


pytestmark = pytest.mark.django_db


# ── Conditional Evaluator ─────────────────────────────────────────────────────

class TestConditionEvaluator:
    """Sicherheits-relevante Tests für den ast-basierten Evaluator."""

    def test_empty_expression_is_true(self):
        assert evaluate('') is True
        assert evaluate('   ') is True

    def test_literal_true(self):
        assert evaluate('True') is True

    def test_comparison(self):
        target = MagicMock(duration=10)
        assert evaluate('target.duration > 5', target=target) is True
        assert evaluate('target.duration < 5', target=target) is False

    def test_attribute_access(self):
        target = MagicMock()
        target.student.course.name = 'IT'
        assert evaluate('target.student.course.name == "IT"', target=target) is True

    def test_in_operator(self):
        target = MagicMock(category='vacation')
        assert evaluate('target.category in ("vacation", "sick")', target=target) is True
        assert evaluate('target.category not in ("foo",)', target=target) is True

    def test_bool_and(self):
        target = MagicMock(duration=10, type='study')
        assert evaluate(
            'target.duration > 5 and target.type == "study"',
            target=target,
        ) is True

    def test_dunder_attribute_forbidden(self):
        target = MagicMock()
        with pytest.raises(ConditionError):
            evaluate('target.__class__', target=target)

    def test_function_call_forbidden(self):
        with pytest.raises(ConditionError):
            evaluate('open("/etc/passwd")')

    def test_unknown_name_forbidden(self):
        with pytest.raises(ConditionError):
            evaluate('os.system("ls")')

    def test_safe_evaluate_returns_default_on_error(self):
        # Syntaxfehler → default
        assert safe_evaluate('!!invalid!!', default=True) is True
        assert safe_evaluate('!!invalid!!', default=False) is False

    def test_none_attribute_short_circuits(self):
        target = MagicMock()
        target.missing = None
        # Zugriff auf .x von None → None (kein Crash)
        assert evaluate('target.missing.x == "y"', target=target) is False


# ── Engine: Lifecycle ──────────────────────────────────────────────────────────

@pytest.fixture
def simple_workflow(db):
    """Workflow mit zwei Stufen ohne Berechtigungs-Prüfung."""
    wd = WorkflowDefinition.objects.create(
        code='test_simple',
        name='Test-Workflow',
        reject_behavior=REJECT_BEHAVIOR_FINAL,
    )
    WorkflowStep.objects.create(
        workflow=wd, order=1, name='Stufe 1',
        approver_type='role', approver_value='training_director',
    )
    WorkflowStep.objects.create(
        workflow=wd, order=2, name='Stufe 2',
        approver_type='role', approver_value='training_director',
    )
    return wd


@pytest.fixture
def director_user(db):
    user = User.objects.create_user(username='director', password='x')
    group, _ = Group.objects.get_or_create(name='ausbildungsleitung')
    user.groups.add(group)
    return user


@pytest.fixture
def target_definition(db):
    """Ein beliebiges Modell-Objekt als Workflow-Ziel.
    Wir nutzen WorkflowDefinition selbst (jedes ContentType-fähige Modell tut's).
    """
    return WorkflowDefinition.objects.create(
        code='__test_target__',
        name='Test-Ziel',
    )


class TestStartWorkflow:

    def test_starts_in_progress_on_first_step(self, simple_workflow, target_definition):
        instance = start_workflow('test_simple', target=target_definition)
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        assert instance.current_step.order == 1
        # Submit-Transition wurde geschrieben
        assert WorkflowTransition.objects.filter(instance=instance).count() == 1

    def test_unknown_workflow_raises(self, target_definition):
        with pytest.raises(WorkflowError):
            start_workflow('does_not_exist', target=target_definition)

    def test_workflow_without_steps_raises(self, target_definition):
        WorkflowDefinition.objects.create(code='no_steps', name='leer')
        with pytest.raises(WorkflowError):
            start_workflow('no_steps', target=target_definition)


class TestApprovalChain:

    def test_approve_advances_to_next_step(self, simple_workflow, target_definition, director_user):
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        perform_action(instance, actor=director_user, action=ACTION_APPROVE,
                       comment='ok')
        instance.refresh_from_db()
        assert instance.current_step.order == 2
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS

    def test_final_approve_finishes_instance(self, simple_workflow, target_definition, director_user):
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        perform_action(instance, actor=director_user, action=ACTION_APPROVE)
        perform_action(instance, actor=director_user, action=ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_APPROVED
        assert instance.current_step is None
        assert instance.finished_at is not None


class TestRejectBehaviors:

    def test_reject_final(self, simple_workflow, target_definition, director_user):
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        perform_action(instance, actor=director_user, action=ACTION_REJECT,
                       comment='nope')
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_REJECTED
        assert instance.current_step is None

    def test_reject_to_first_resets_step(self, simple_workflow, target_definition, director_user):
        simple_workflow.reject_behavior = REJECT_BEHAVIOR_TO_FIRST
        simple_workflow.save()
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        perform_action(instance, actor=director_user, action=ACTION_APPROVE)
        instance.refresh_from_db()
        assert instance.current_step.order == 2
        old_revision = instance.revision

        perform_action(instance, actor=director_user, action=ACTION_REJECT,
                       comment='back to start')
        instance.refresh_from_db()
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        assert instance.current_step.order == 1
        assert instance.revision == old_revision + 1

    def test_reject_to_initiator_pauses(self, simple_workflow, target_definition, director_user):
        simple_workflow.reject_behavior = REJECT_BEHAVIOR_TO_INITIATOR
        simple_workflow.save()
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        perform_action(instance, actor=director_user, action=ACTION_REJECT,
                       comment='please rework')
        instance.refresh_from_db()
        # Status bleibt in_progress, aber current_step ist None
        assert instance.status == INSTANCE_STATUS_IN_PROGRESS
        assert instance.current_step is None

        # Resubmit setzt zurück auf Stufe 1
        perform_action(instance, actor=director_user, action=ACTION_RESUBMIT,
                       comment='überarbeitet')
        instance.refresh_from_db()
        assert instance.current_step.order == 1


class TestPreCondition:

    def test_unmet_pre_condition_auto_approves(self, simple_workflow, target_definition, director_user):
        # Pre-Condition, die nicht erfüllt ist → sofort auto-approved
        simple_workflow.pre_condition = 'target.bogus_flag == True'
        simple_workflow.save()
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        assert instance.status == INSTANCE_STATUS_APPROVED


class TestSkipCondition:

    def test_step_is_skipped_when_condition_true(self, simple_workflow, target_definition, director_user):
        step1 = simple_workflow.steps.get(order=1)
        step1.skip_condition = 'True'
        step1.save()
        instance = start_workflow('test_simple', target=target_definition,
                                  initiator=director_user)
        instance.refresh_from_db()
        # Stufe 1 übersprungen → direkt auf Stufe 2
        assert instance.current_step.order == 2


class TestCompletionHooks:

    def test_hook_called_on_final_approve(self, simple_workflow, target_definition, director_user):
        _COMPLETION_HOOKS.pop('test_simple', None)  # alte Hooks entfernen
        seen = []

        def hook(instance, status):
            seen.append((instance.pk, status))

        register_completion_hook('test_simple', hook)
        try:
            instance = start_workflow('test_simple', target=target_definition,
                                      initiator=director_user)
            perform_action(instance, actor=director_user, action=ACTION_APPROVE)
            perform_action(instance, actor=director_user, action=ACTION_APPROVE)
            assert seen == [(instance.pk, INSTANCE_STATUS_APPROVED)]
        finally:
            _COMPLETION_HOOKS.pop('test_simple', None)

    def test_hook_exception_does_not_break_engine(self, simple_workflow, target_definition, director_user):
        _COMPLETION_HOOKS.pop('test_simple', None)

        def bad_hook(instance, status):
            raise RuntimeError('Boom!')

        register_completion_hook('test_simple', bad_hook)
        try:
            instance = start_workflow('test_simple', target=target_definition,
                                      initiator=director_user)
            perform_action(instance, actor=director_user, action=ACTION_APPROVE)
            # Final approve — Hook wirft, aber Engine schließt sauber ab
            perform_action(instance, actor=director_user, action=ACTION_APPROVE)
            instance.refresh_from_db()
            assert instance.status == INSTANCE_STATUS_APPROVED
        finally:
            _COMPLETION_HOOKS.pop('test_simple', None)


class TestGetInstanceFor:

    def test_returns_most_recent(self, simple_workflow, target_definition, director_user):
        inst1 = start_workflow('test_simple', target=target_definition,
                                initiator=director_user)
        result = get_instance_for(target_definition)
        assert result.pk == inst1.pk
