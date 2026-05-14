"""Admin-UI für die Workflow-Engine.

Nur für Ausbildungsleitung. Erlaubt das Anlegen/Bearbeiten von
``WorkflowDefinition`` und das Hinzufügen/Verschieben/Löschen von
``WorkflowStep``-Einträgen.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from services.roles import is_training_director
from django.contrib.auth.decorators import user_passes_test

from .models import (
    WorkflowDefinition, WorkflowStep,
    APPROVER_TYPE_CHOICES, TIMEOUT_CHOICES, REJECT_BEHAVIOR_CHOICES,
)


def director_required(view_fn):
    return login_required(user_passes_test(is_training_director)(view_fn))


@director_required
def workflow_list(request):
    definitions = WorkflowDefinition.objects.prefetch_related('steps').order_by('name')
    return render(request, 'workflow/list.html', {
        'definitions': definitions,
    })


@director_required
def workflow_edit(request, code):
    definition = get_object_or_404(WorkflowDefinition, code=code)

    if request.method == 'POST':
        definition.name = request.POST.get('name', definition.name).strip()
        definition.description = request.POST.get('description', '').strip()
        definition.is_active = request.POST.get('is_active') == 'on'
        definition.pre_condition = request.POST.get('pre_condition', '').strip()
        definition.reject_behavior = request.POST.get('reject_behavior',
                                                       definition.reject_behavior)
        definition.save()
        messages.success(request, f'Workflow „{definition.name}" gespeichert.')
        return redirect('workflow:edit', code=definition.code)

    return render(request, 'workflow/edit.html', {
        'definition': definition,
        'steps': definition.active_steps(),
        'approver_type_choices': APPROVER_TYPE_CHOICES,
        'timeout_choices': TIMEOUT_CHOICES,
        'reject_behavior_choices': REJECT_BEHAVIOR_CHOICES,
    })


@director_required
@require_POST
def step_add(request, code):
    definition = get_object_or_404(WorkflowDefinition, code=code)
    last = definition.steps.order_by('-order').first()
    next_order = (last.order + 1) if last else 1

    step = WorkflowStep.objects.create(
        workflow=definition,
        order=next_order,
        name=request.POST.get('name', 'Neue Stufe').strip(),
        approver_type=request.POST.get('approver_type', 'role'),
        approver_value=request.POST.get('approver_value', '').strip(),
        deadline_days=request.POST.get('deadline_days') or None,
        on_timeout=request.POST.get('on_timeout', 'remind'),
        escalate_to_value=request.POST.get('escalate_to_value', '').strip(),
        skip_condition=request.POST.get('skip_condition', '').strip(),
    )
    messages.success(request, f'Stufe „{step.name}" angelegt.')
    return redirect('workflow:edit', code=definition.code)


@director_required
@require_POST
def step_edit(request, step_pk):
    step = get_object_or_404(WorkflowStep, pk=step_pk)
    step.name = request.POST.get('name', step.name).strip()
    step.approver_type = request.POST.get('approver_type', step.approver_type)
    step.approver_value = request.POST.get('approver_value', '').strip()
    step.deadline_days = request.POST.get('deadline_days') or None
    step.on_timeout = request.POST.get('on_timeout', step.on_timeout)
    step.escalate_to_value = request.POST.get('escalate_to_value', '').strip()
    step.skip_condition = request.POST.get('skip_condition', '').strip()
    step.save()
    messages.success(request, f'Stufe „{step.name}" gespeichert.')
    return redirect('workflow:edit', code=step.workflow.code)


@director_required
@require_POST
def step_delete(request, step_pk):
    step = get_object_or_404(WorkflowStep, pk=step_pk)
    code = step.workflow.code
    name = step.name
    step.delete()
    messages.success(request, f'Stufe „{name}" gelöscht.')
    return redirect('workflow:edit', code=code)


@director_required
@require_POST
def step_move(request, step_pk, direction):
    step = get_object_or_404(WorkflowStep, pk=step_pk)
    if direction == 'up':
        prev = step.workflow.steps.filter(order__lt=step.order).order_by('-order').first()
        if prev:
            step.order, prev.order = prev.order, step.order
            # Zwischenwert verwenden um unique_together-Konflikt zu vermeiden
            prev_order = prev.order
            step_order = step.order
            prev.order = -1
            prev.save(update_fields=['order'])
            step.order = step_order
            step.save(update_fields=['order'])
            prev.order = prev_order
            prev.save(update_fields=['order'])
    elif direction == 'down':
        nxt = step.workflow.steps.filter(order__gt=step.order).order_by('order').first()
        if nxt:
            prev_order = nxt.order
            step_order = step.order
            nxt.order = -1
            nxt.save(update_fields=['order'])
            step.order = prev_order
            step.save(update_fields=['order'])
            nxt.order = step_order
            nxt.save(update_fields=['order'])

    return redirect('workflow:edit', code=step.workflow.code)
