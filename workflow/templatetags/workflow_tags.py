"""Template-Tags für die Workflow-Engine."""
from django import template

from ..engine import can_act, deadline_for, get_instance_for
from ..approvers import get_step_approver_label

register = template.Library()


@register.inclusion_tag('workflow/_history.html', takes_context=True)
def workflow_history(context, target=None, instance=None):
    """Rendert die Verlaufs-Anzeige für ein Workflow-Ziel oder eine Instanz."""
    if instance is None and target is not None:
        instance = get_instance_for(target)
    user = context.get('user') or context.get('request', {}).user if 'request' in context else None
    return {
        'instance': instance,
        'transitions': instance.transitions.select_related('step', 'actor').all() if instance else [],
        'can_act': can_act(instance, user) if instance and user else False,
        'deadline': deadline_for(instance) if instance else None,
        'current_step_approver_label': (
            get_step_approver_label(instance.current_step, instance.target)
            if instance and instance.current_step else ''
        ),
    }


@register.simple_tag
def workflow_for(target):
    """Gibt die aktuelle WorkflowInstance eines Zielobjekts zurück."""
    return get_instance_for(target)


@register.simple_tag
def workflow_can_act(instance, user):
    """Prüft, ob ``user`` die aktuelle Stufe entscheiden darf."""
    return can_act(instance, user) if instance else False


@register.simple_tag
def workflow_approver_label(instance):
    """Liefert eine menschenlesbare Beschreibung des aktuellen Approvers."""
    if not instance or not instance.current_step:
        return ''
    return get_step_approver_label(instance.current_step, instance.target)
