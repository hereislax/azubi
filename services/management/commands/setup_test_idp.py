# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Konfiguriert das lokale Keycloak-Test-Setup im Azubi-Portal.

Pendant zu ``docker/keycloak-test.compose.yml`` und
``docker/keycloak-test-realm.json``: legt eine ``SocialApp`` für den
Realm ``behoerde-a`` an und erstellt einen Portal-User mit der E-Mail,
auf die der Test-User in Keycloak gemappt wird.

Das Kommando ist idempotent – mehrmals aufrufen ist unproblematisch.

    python manage.py setup_test_idp

Anschließend lässt sich der gesamte SSO-Flow lokal testen:

    docker compose -f docker/keycloak-test.compose.yml up -d
    python manage.py setup_test_idp
    python manage.py runserver 0.0.0.0:8080
    # http://localhost:8080/accounts/login/ -> "Anmelden mit Behörde A"
    # Login: testuser / Testpass1!
"""
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


PROVIDER_ID = 'behoerde-a'
PROVIDER_NAME = 'Behörde A (Test)'
CLIENT_ID = 'azubi-portal'
CLIENT_SECRET = 'azubi-test-secret-only-for-dev'
ISSUER_URL = 'http://localhost:8090/realms/behoerde-a'
ALLOWED_DOMAINS = ['behoerde-a.test']

PORTAL_USER_USERNAME = 'testuser'
PORTAL_USER_EMAIL = 'testuser@behoerde-a.test'
PORTAL_USER_FIRSTNAME = 'Test'
PORTAL_USER_LASTNAME = 'User'


class Command(BaseCommand):
    help = (
        'Legt SocialApp + Portal-User für das Keycloak-Dev-Setup an. '
        'Erwartet, dass docker/keycloak-test.compose.yml gestartet ist.'
    )

    def handle(self, *args, **options):
        from allauth.socialaccount.models import SocialApp

        site = Site.objects.get(pk=1)

        app, app_created = SocialApp.objects.update_or_create(
            provider='openid_connect',
            provider_id=PROVIDER_ID,
            defaults={
                'name': PROVIDER_NAME,
                'client_id': CLIENT_ID,
                'secret': CLIENT_SECRET,
                'settings': {
                    'server_url': ISSUER_URL,
                    'allowed_email_domains': ALLOWED_DOMAINS,
                },
            },
        )
        app.sites.add(site)
        self.stdout.write(self.style.SUCCESS(
            f'SocialApp "{PROVIDER_NAME}" {"angelegt" if app_created else "aktualisiert"}.'
        ))

        # Portal-User mit zur Keycloak-Mail passender Adresse anlegen.
        # Wichtig: KEIN nutzbares Passwort setzen – der User soll ausschließlich
        # über SSO einloggen können. Wer das ändern will, kann via
        # /accounts/password_reset/ ein lokales Passwort setzen.
        user, user_created = User.objects.update_or_create(
            username=PORTAL_USER_USERNAME,
            defaults={
                'email': PORTAL_USER_EMAIL,
                'first_name': PORTAL_USER_FIRSTNAME,
                'last_name': PORTAL_USER_LASTNAME,
                'is_active': True,
            },
        )
        if user_created or not user.has_usable_password():
            user.set_unusable_password()
            user.save(update_fields=['password'])
        self.stdout.write(self.style.SUCCESS(
            f'Portal-User "{PORTAL_USER_USERNAME}" '
            f'{"angelegt" if user_created else "aktualisiert"} '
            f'(E-Mail: {PORTAL_USER_EMAIL}).'
        ))

        self.stdout.write('')
        self.stdout.write('SSO-Test bereit:')
        self.stdout.write(f'  Keycloak-Admin:     http://localhost:8090  (admin/admin)')
        self.stdout.write(f'  Issuer:             {ISSUER_URL}')
        self.stdout.write(f'  Allowed-Domains:    {ALLOWED_DOMAINS}')
        self.stdout.write('')
        self.stdout.write('Test-Logins (in Keycloak einzugeben):')
        self.stdout.write('  testuser / Testpass1!         -> sollte erfolgreich verknüpfen')
        self.stdout.write('  fremde-domain / Testpass1!    -> sollte mit "domain_not_allowed" abgelehnt werden')
        self.stdout.write('')
        self.stdout.write('Für den negativen "no_local_account"-Fall:')
        self.stdout.write('  In Keycloak einen User mit Mail @behoerde-a.test anlegen,')
        self.stdout.write('  der KEIN Pendant in der Azubi-DB hat.')
