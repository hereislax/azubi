# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html, mark_safe

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

import axes.admin  # noqa: F401 – stellt sicher, dass axes seinen Admin registriert,
                   # bevor wir hier unregister/register überschreiben.
from axes.models import AccessAttempt

from auditlog.manual import log_event
from auditlog.models import AuditLogEntry

from .models import Adress, NotificationTemplate, NOTIFICATION_VARIABLES, UserProfile


@admin.register(Adress)
class AdressAdmin(admin.ModelAdmin):
    list_display = ("street", "house_number", "zip_code", "city")
    search_fields = ("street", "city")


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['get_key_display', 'subject']
    readonly_fields = ['key', 'available_variables']
    fields = ['key', 'available_variables', 'subject', 'body']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Verfügbare Variablen')
    def available_variables(self, obj):
        variables = NOTIFICATION_VARIABLES.get(obj.key, [])
        if not variables:
            return '–'

        rows = ''
        for name, desc in variables:
            code = f'{{{{ {name} }}}}'
            rows += (
                f'<tr>'
                f'<td style="padding:2px 12px 2px 0;font-family:monospace;white-space:nowrap">'
                f'<code style="background:#f0f0f0;padding:1px 6px;border-radius:3px">{code}</code>'
                f'</td>'
                f'<td style="padding:2px 0;color:#555">{desc}</td>'
                f'</tr>'
            )

        return mark_safe(
            '<table style="border-collapse:collapse;margin-top:4px">'
            '<thead><tr>'
            '<th style="text-align:left;padding:2px 12px 4px 0;color:#333">Variable</th>'
            '<th style="text-align:left;padding:2px 0 4px 0;color:#333">Bedeutung</th>'
            '</tr></thead>'
            f'<tbody>{rows}</tbody>'
            '</table>'
        )


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Profil"
    fields = ('job_title', 'location', 'room', 'phone')


admin.site.unregister(User)

RESET_2FA_PERM = 'services.reset_user_2fa'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    actions = ['reset_2fa']

    def get_actions(self, request):
        """Blende Reset-Action für User ohne dedizierte Permission aus."""
        actions = super().get_actions(request)
        if not request.user.has_perm(RESET_2FA_PERM):
            actions.pop('reset_2fa', None)
        return actions

    @admin.action(description='2FA zurücksetzen (mit Audit-Eintrag)')
    def reset_2fa(self, request, queryset):
        """Löscht alle TOTP- und Static-Devices der ausgewählten User.

        Erfordert die Permission ``services.reset_user_2fa``. Sie wird über
        UserProfile.Meta.permissions definiert und kann in einer eigenen
        "Sicherheits-Admin"-Gruppe an wenige Personen vergeben werden.

        Auto-Tracking schreibt pro Device einen DELETE-Eintrag (siehe
        auditlog.registry.TRACKED_FIELDS); zusätzlich vermerken wir hier
        explizit, dass die Reset-Aktion durch einen Admin ausgelöst wurde.
        """
        # Defensiver Permission-Check, falls jemand die Action via direkter
        # POST-Anfrage triggert (Bypass des Dropdown-Filters).
        if not request.user.has_perm(RESET_2FA_PERM):
            self.message_user(
                request,
                'Sie haben keine Berechtigung, 2FA für Benutzer zurückzusetzen.',
                level=messages.ERROR,
            )
            return

        from django_otp.plugins.otp_totp.models import TOTPDevice
        from django_otp.plugins.otp_static.models import StaticDevice

        affected = 0
        skipped = 0
        with transaction.atomic():
            for user in queryset:
                had_totp = TOTPDevice.objects.filter(user=user).exists()
                had_static = StaticDevice.objects.filter(user=user).exists()
                if not (had_totp or had_static):
                    skipped += 1
                    continue

                log_event(
                    action=AuditLogEntry.ACTION_UPDATE,
                    instance=user,
                    user=request.user,
                    changes={
                        '2FA': {'old': 'aktiv', 'new': 'durch Admin zurückgesetzt'},
                        'reset_by': request.user.username,
                    },
                )

                TOTPDevice.objects.filter(user=user).delete()
                StaticDevice.objects.filter(user=user).delete()
                affected += 1

        parts = [f'2FA für {affected} Benutzer zurückgesetzt.']
        if skipped:
            parts.append(f'{skipped} Benutzer hatten kein 2FA – übersprungen.')
        self.message_user(request, ' '.join(parts), level=messages.SUCCESS)


# ---------------------------------------------------------------------------
# axes.AccessAttempt – Override mit Entsperren-Action und Audit-Eintrag
# ---------------------------------------------------------------------------
admin.site.unregister(AccessAttempt)


@admin.register(AccessAttempt)
class AccessAttemptAdmin(admin.ModelAdmin):
    """Lockout-Verwaltung mit explizitem Audit-Trail beim Entsperren."""

    list_display = ('username', 'ip_address', 'failures_since_start', 'attempt_time')
    list_filter = ('attempt_time',)
    search_fields = ('username', 'ip_address')
    readonly_fields = (
        'username', 'ip_address', 'user_agent', 'http_accept',
        'path_info', 'attempt_time', 'failures_since_start',
        'get_data', 'post_data',
    )
    actions = ['unlock_accounts']

    def has_add_permission(self, request):
        return False

    @admin.action(description='Konto entsperren (mit Audit-Eintrag)')
    def unlock_accounts(self, request, queryset):
        usernames = sorted({a.username for a in queryset if a.username})
        if not usernames:
            self.message_user(
                request,
                'Keine Benutzernamen in Auswahl – nichts zu entsperren.',
                level=messages.WARNING,
            )
            return

        with transaction.atomic():
            audited = 0
            for username in usernames:
                user = User.objects.filter(username=username).first()
                if user is None:
                    # Lockout für nicht existierenden Username (Tippfehler oder
                    # Angreifer): keine Audit-Verknüpfung möglich, aber Lock
                    # darf trotzdem aufgehoben werden.
                    continue
                log_event(
                    action=AuditLogEntry.ACTION_UNLOCK,
                    instance=user,
                    user=request.user,
                    changes={
                        'unlocked_by': request.user.username,
                        'unlocked_username': username,
                    },
                )
                audited += 1

            # Alle Attempts dieser Usernames löschen, nicht nur die selektierten –
            # sonst bleibt der User von einer anderen IP weiter blockiert.
            deleted, _ = AccessAttempt.objects.filter(username__in=usernames).delete()

        self.message_user(
            request,
            f'{len(usernames)} Konto/Konten entsperrt '
            f'({deleted} Lockout-Einträge entfernt, {audited} Audit-Eintrag/Einträge geschrieben).',
            level=messages.SUCCESS,
        )
