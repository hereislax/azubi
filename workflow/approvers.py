"""Approver-Resolution: Wer darf eine Workflow-Stufe entscheiden?

Module können eigene **dynamische Resolver** registrieren, die anhand des
Workflow-Targets den zuständigen Approver-User ermitteln (z.B. „Praxistutor
des Einsatzes, an dem dieser Ausbildungsnachweis hängt").
"""
from typing import Callable, Optional, Iterable

from django.contrib.auth import get_user_model

User = get_user_model()


# ── Rollen-Registry ────────────────────────────────────────────────────────
# Wird vom Modul-Code beim Start gefüllt (apps.py ready()).
# Mapping: role_code → callable(user) -> bool
_ROLE_REGISTRY: dict[str, Callable] = {}


def register_role(code: str, check_fn: Callable):
    """Registriert eine Rollen-Prüf-Funktion."""
    _ROLE_REGISTRY[code] = check_fn


def role_check(code: str, user):
    """Prüft, ob ``user`` die Rolle ``code`` hat. Unbekannte Codes → False."""
    check = _ROLE_REGISTRY.get(code)
    return bool(check and check(user))


def users_with_role(code: str) -> Iterable:
    """Iteriert über alle aktiven User, die ``code`` haben.

    Effizient nur über die Django-Group, daher Konvention: ``code`` ist auch
    der Group-Name. Fallback: alle User durchgehen.
    """
    qs = User.objects.filter(is_active=True)
    # Group-basierte Rollen (Standard im Portal): code == group name
    return qs.filter(groups__name=code).distinct()


# ── Dynamische Resolver-Registry ───────────────────────────────────────────
# Mapping: resolver_code → callable(target) -> Optional[User]
_DYNAMIC_REGISTRY: dict[str, Callable] = {}


def register_dynamic(code: str, resolver_fn: Callable):
    """Registriert einen dynamischen Approver-Resolver.

    Beispiel: ``register_dynamic('proof_of_training.instructor',
                                  lambda record: record.assignment.instructor.user)``
    """
    _DYNAMIC_REGISTRY[code] = resolver_fn


def resolve_dynamic(code: str, target) -> Optional[User]:
    """Löst einen dynamischen Approver auf. Unbekannter Code → None."""
    fn = _DYNAMIC_REGISTRY.get(code)
    return fn(target) if fn else None


# ── Step-Approver-Auflösung ────────────────────────────────────────────────

def can_approve_step(step, user, target) -> bool:
    """Prüft, ob ``user`` die ``step`` für ``target`` entscheiden kann."""
    from .models import APPROVER_ROLE, APPROVER_USER, APPROVER_DYNAMIC, \
        APPROVER_EXTERNAL_TOKEN, APPROVER_INFO

    if not user or not user.is_authenticated:
        return False

    if step.approver_type == APPROVER_ROLE:
        return role_check(step.approver_value, user)

    if step.approver_type == APPROVER_USER:
        try:
            return user.pk == int(step.approver_value)
        except (ValueError, TypeError):
            return False

    if step.approver_type == APPROVER_DYNAMIC:
        resolved = resolve_dynamic(step.approver_value, target)
        return resolved is not None and resolved.pk == user.pk

    if step.approver_type == APPROVER_EXTERNAL_TOKEN:
        # Externe Token-Approver loggen sich nicht ein → über Token-View
        return False

    if step.approver_type == APPROVER_INFO:
        # Info-Steps: Jeder, der den Resolver erfüllt, darf abzeichnen.
        # ``approver_value`` enthält hier die Rolle (z.B. „coordination").
        return role_check(step.approver_value, user)

    return False


def get_step_approver_label(step, target=None) -> str:
    """Liefert eine menschenlesbare Beschreibung des Step-Approvers (für UI)."""
    from .models import APPROVER_ROLE, APPROVER_USER, APPROVER_DYNAMIC, \
        APPROVER_EXTERNAL_TOKEN, APPROVER_INFO

    if step.approver_type == APPROVER_ROLE:
        return f'Rolle „{step.approver_value}"'
    if step.approver_type == APPROVER_USER:
        try:
            u = User.objects.filter(pk=int(step.approver_value)).first()
            return u.get_full_name() if u else f'User #{step.approver_value}'
        except (ValueError, TypeError):
            return '–'
    if step.approver_type == APPROVER_DYNAMIC:
        if target:
            u = resolve_dynamic(step.approver_value, target)
            if u:
                return u.get_full_name() or u.username
        return f'Dynamisch ({step.approver_value})'
    if step.approver_type == APPROVER_EXTERNAL_TOKEN:
        return f'Extern via Token-Link ({step.approver_value})'
    if step.approver_type == APPROVER_INFO:
        return f'Info an Rolle „{step.approver_value}"'
    return '–'
