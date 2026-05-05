# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Custom-Adapter für allauth-SSO-Logins.

Erzwingt die im Auth-Konzept festgelegten Regeln:

* SSO darf NIEMALS automatisch User anlegen (kein JIT-Provisioning).
* Pro IdP wird eine optionale E-Mail-Domain-Whitelist geprüft (in
  ``SocialApp.settings['allowed_email_domains']`` als Liste).
* Bei erstmaliger Anmeldung wird über Case-insensitive-E-Mail-Match auf
  einen bestehenden lokalen Benutzer verknüpft.
* Bei jedem Fehlerfall wird auf eine sprechende Fehlerseite umgeleitet,
  ohne Existenz von E-Mail-Adressen oder Konten zu bestätigen.
* Fehlversuche werden ins Audit-Log geschrieben (Aktion LOGIN_FAILED).
"""
import logging

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.urls import reverse

from auditlog.models import AuditLogEntry

logger = logging.getLogger(__name__)


class AzubiSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Steuert den allauth-OIDC-Flow nach Behörden-Vorgaben."""

    def is_open_for_signup(self, request, sociallogin):
        # Kein JIT, niemals.
        return False

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            # Bereits verknüpfter Account → allauth loggt regulär ein.
            return

        email = (sociallogin.user.email or '').strip().lower()
        provider = sociallogin.account.get_provider(request)
        provider_label = getattr(provider, 'name', '') or provider.id
        app = getattr(provider, 'app', None)

        if not email:
            logger.warning('SSO-Login ohne E-Mail-Claim von Provider %s', provider_label)
            raise ImmediateHttpResponse(self._error_redirect('no_email'))

        # ── Domain-Whitelist ──────────────────────────────────────────────
        app_settings = (app.settings if app else {}) or {}
        allowed_domains = [
            d.lower().lstrip('@')
            for d in app_settings.get('allowed_email_domains', [])
            if d
        ]
        if allowed_domains:
            domain = email.rsplit('@', 1)[-1]
            if domain not in allowed_domains:
                logger.warning(
                    'SSO-Login mit Domain "%s" außerhalb der Whitelist von %s',
                    domain, provider_label,
                )
                self._audit_failure(email, provider_label, app, reason='domain_not_allowed')
                raise ImmediateHttpResponse(self._error_redirect('domain_not_allowed'))

        # ── Match auf bestehenden lokalen Benutzer ────────────────────────
        User = get_user_model()
        matches = list(User.objects.filter(email__iexact=email)[:2])

        if not matches:
            self._audit_failure(email, provider_label, app, reason='no_local_account')
            raise ImmediateHttpResponse(self._error_redirect('no_local_account'))

        if len(matches) > 1:
            # Mehrdeutigkeit ist ein Datenpflege-Fehler, nicht der Fehler des Users.
            logger.error(
                'SSO-Login: %d lokale Konten zur E-Mail %s gefunden – uneindeutig',
                len(matches), email,
            )
            self._audit_failure(email, provider_label, app, reason='multiple_local_accounts')
            raise ImmediateHttpResponse(self._error_redirect('multiple_local_accounts'))

        user = matches[0]
        if not user.is_active:
            self._audit_failure(email, provider_label, app, reason='inactive')
            raise ImmediateHttpResponse(self._error_redirect('no_local_account'))

        # ── Verknüpfen ────────────────────────────────────────────────────
        # connect() speichert die SocialAccount und schließt allauth-seitig
        # an den Login-Flow an (user_logged_in-Signal feuert → Audit-Log
        # ACTION_LOGIN wird automatisch geschrieben).
        sociallogin.connect(request, user)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _error_redirect(reason):
        return HttpResponseRedirect(f"{reverse('sso_error')}?reason={reason}")

    @staticmethod
    def _audit_failure(email, provider_label, app, *, reason):
        """Schreibt einen Audit-Eintrag, ohne lokales Konto zu referenzieren.

        Wir verwenden ``SocialApp`` als Träger-Objekt (die IdP-Konfiguration),
        damit der Eintrag im Audit-Log filterbar bleibt. Die eigentliche
        Information landet in ``object_repr`` und ``changes``.
        """
        try:
            AuditLogEntry.objects.create(
                user=None,
                action=AuditLogEntry.ACTION_LOGIN_FAILED,
                app_label='socialaccount',
                model_name='socialapp',
                model_verbose_name='Soziale Anwendung',
                object_id=str(app.pk) if app else '',
                object_repr=f'SSO-Versuch über {provider_label}: {email} ({reason})',
                changes={
                    'reason': reason,
                    'email': email,
                    'provider': provider_label,
                },
            )
        except Exception:
            logger.exception('auditlog: failed to log SSO failure for %s', email)
