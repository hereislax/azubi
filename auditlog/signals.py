# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Django signal handlers that write AuditLogEntry records whenever a tracked
model is created, updated, or deleted.
"""
import logging
from django.apps import apps
from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed,
)
from django.db.models.signals import pre_save, post_save, post_delete

from .registry import TRACKED_FIELDS, _student_id_from_instance
from .middleware import get_current_user

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    """Extract the client IP, honoring X-Forwarded-For for proxied requests."""
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request):
    if request is None:
        return None
    return request.META.get('HTTP_USER_AGENT', '') or None


# ── Value serialization ───────────────────────────────────────────────────────

def _serialize_value(instance, field_name):
    """Return a human-readable string value for a field on a model instance."""
    try:
        meta_field = instance._meta.get_field(field_name)
    except Exception:
        return None

    raw = getattr(instance, field_name, None)
    if raw is None:
        return None

    # FK / OneToOne: __str__ des verknüpften Objekts verwenden (bereits geladen oder per PK)
    if hasattr(meta_field, 'related_model') and meta_field.related_model is not None:
        try:
            related_obj = getattr(instance, field_name)
            return str(related_obj) if related_obj is not None else None
        except Exception:
            return str(raw)

    # Choices-Feld: lesbares Label zurückgeben
    choices = getattr(meta_field, 'choices', None)
    if choices:
        choices_dict = dict(choices)
        return choices_dict.get(raw, str(raw))

    # Date / datetime
    if hasattr(raw, 'strftime'):
        if hasattr(raw, 'hour'):
            from django.utils import timezone
            # Zeitzonenbewusstes Datum für die Anzeige in Lokalzeit umwandeln
            try:
                import pytz
                from django.conf import settings as dj_settings
                tz = pytz.timezone(dj_settings.TIME_ZONE)
                raw = raw.astimezone(tz)
            except Exception:
                pass
            return raw.strftime('%d.%m.%Y %H:%M')
        return raw.strftime('%d.%m.%Y')

    # Boolean
    if isinstance(raw, bool):
        return 'Ja' if raw else 'Nein'

    return str(raw) if raw != '' else None


def _get_field_values(instance, field_names):
    """Return a dict of {field_name: serialized_value} for the given fields."""
    return {
        field_name: _serialize_value(instance, field_name)
        for field_name in field_names
    }


# ── Signal handlers ───────────────────────────────────────────────────────────

def _pre_save_handler(sender, instance, **kwargs):
    """Capture field values from the database BEFORE the save."""
    key = (sender._meta.app_label, sender._meta.model_name)
    field_names = TRACKED_FIELDS.get(key)
    if field_names is None:
        return

    if not instance.pk:
        instance._audit_is_new = True
        instance._audit_old_values = {}
        return

    try:
        old = sender.objects.get(pk=instance.pk)
        instance._audit_is_new = False
        instance._audit_old_values = _get_field_values(old, field_names)
    except sender.DoesNotExist:
        instance._audit_is_new = True
        instance._audit_old_values = {}


def _post_save_handler(sender, instance, created, **kwargs):
    """Compare old vs new values and write an AuditLogEntry."""
    key = (sender._meta.app_label, sender._meta.model_name)
    field_names = TRACKED_FIELDS.get(key)
    if field_names is None:
        return

    new_values = _get_field_values(instance, field_names)
    old_values = getattr(instance, '_audit_old_values', {})
    is_new = getattr(instance, '_audit_is_new', created)

    if is_new:
        action = 'create'
        # For creates, log all non-empty fields as changes
        changes = {
            k: {'old': None, 'new': v}
            for k, v in new_values.items()
            if v is not None and v != ''
        }
    else:
        action = 'update'
        changes = {}
        for field_name in field_names:
            old_val = old_values.get(field_name)
            new_val = new_values.get(field_name)
            if old_val != new_val:
                verbose = _verbose_field_name(sender, field_name)
                changes[verbose] = {'old': old_val, 'new': new_val}
        if not changes:
            return  # Nichts hat sich tatsächlich geändert – überspringen

        # Bei Neuanlagen die Änderungen mit lesbaren Feldnamen neu aufbauen
        # (für Updates erfolgt dieser Schritt bereits weiter oben)
    if is_new:
        changes = {}
        for field_name in field_names:
            new_val = new_values.get(field_name)
            if new_val is not None and new_val != '':
                verbose = _verbose_field_name(sender, field_name)
                changes[verbose] = {'old': None, 'new': new_val}

    _write_log(
        action=action,
        sender=sender,
        instance=instance,
        changes=changes,
    )


def _post_delete_handler(sender, instance, **kwargs):
    """Write a DELETE AuditLogEntry."""
    key = (sender._meta.app_label, sender._meta.model_name)
    if key not in TRACKED_FIELDS:
        return

    _write_log(
        action='delete',
        sender=sender,
        instance=instance,
        changes={},
    )


def _verbose_field_name(model_class, field_name):
    """Return the verbose_name for a field, falling back to field_name."""
    try:
        return str(model_class._meta.get_field(field_name).verbose_name).capitalize()
    except Exception:
        return field_name


def _write_log(action, sender, instance, changes):
    """Persist an AuditLogEntry."""
    from .models import AuditLogEntry
    try:
        AuditLogEntry.objects.create(
            user=get_current_user(),
            action=action,
            app_label=sender._meta.app_label,
            model_name=sender._meta.model_name,
            model_verbose_name=str(sender._meta.verbose_name),
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes=changes,
            student_id=_student_id_from_instance(instance),
        )
    except Exception:
        logger.exception("auditlog: failed to write log entry for %s %s", sender, instance.pk)


# ── Auth signal handlers (Anmeldung / Abmeldung / Fehlversuch) ────────────────

def _login_handler(sender, request, user, **kwargs):
    from .models import AuditLogEntry
    try:
        AuditLogEntry.objects.create(
            user=user,
            action=AuditLogEntry.ACTION_LOGIN,
            app_label='auth',
            model_name='user',
            model_verbose_name='Anmeldung',
            object_id=str(user.pk) if user else '',
            object_repr=user.get_full_name() or user.get_username() if user else '',
            changes={
                'IP-Adresse':  {'old': None, 'new': _get_client_ip(request) or '–'},
                'User-Agent':  {'old': None, 'new': _get_user_agent(request) or '–'},
            },
            student_id=None,
        )
    except Exception:
        logger.exception("auditlog: failed to log user_logged_in for %s", user)


def _logout_handler(sender, request, user, **kwargs):
    from .models import AuditLogEntry
    # user kann None sein, wenn die Session bereits abgelaufen war
    if user is None:
        return
    try:
        AuditLogEntry.objects.create(
            user=user,
            action=AuditLogEntry.ACTION_LOGOUT,
            app_label='auth',
            model_name='user',
            model_verbose_name='Abmeldung',
            object_id=str(user.pk),
            object_repr=user.get_full_name() or user.get_username(),
            changes={
                'IP-Adresse': {'old': None, 'new': _get_client_ip(request) or '–'},
            },
            student_id=None,
        )
    except Exception:
        logger.exception("auditlog: failed to log user_logged_out for %s", user)


def _login_failed_handler(sender, credentials, request=None, **kwargs):
    from .models import AuditLogEntry
    # credentials ist ein dict; das Passwort filtert Django bereits raus.
    attempted = credentials.get('username') or credentials.get('email') or '–'
    try:
        AuditLogEntry.objects.create(
            user=None,
            action=AuditLogEntry.ACTION_LOGIN_FAILED,
            app_label='auth',
            model_name='user',
            model_verbose_name='Anmeldung fehlgeschlagen',
            object_id='',
            object_repr=str(attempted),
            changes={
                'Versuchter Benutzer': {'old': None, 'new': str(attempted)},
                'IP-Adresse':          {'old': None, 'new': _get_client_ip(request) or '–'},
                'User-Agent':          {'old': None, 'new': _get_user_agent(request) or '–'},
            },
            student_id=None,
        )
    except Exception:
        logger.exception("auditlog: failed to log user_login_failed for %s", attempted)


# ── Registration ──────────────────────────────────────────────────────────────

def register_signals():
    """Connect signals for all tracked models. Called from AppConfig.ready()."""
    for app_label, model_name in TRACKED_FIELDS:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            logger.warning("auditlog: model %s.%s not found, skipping", app_label, model_name)
            continue

        pre_save.connect(_pre_save_handler, sender=model, weak=False)
        post_save.connect(_post_save_handler, sender=model, weak=False)
        post_delete.connect(_post_delete_handler, sender=model, weak=False)

    # Auth-Signale: Anmeldung, Abmeldung, Fehlversuch
    user_logged_in.connect(_login_handler, weak=False)
    user_logged_out.connect(_logout_handler, weak=False)
    user_login_failed.connect(_login_failed_handler, weak=False)
