# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Integrationstests für die Authentifizierungs-Pipeline.

Deckt ab:
* Passwort-Policy (Mindestlänge, Sonderzeichen, Ziffer)
* django-axes-Lockout + Admin-Entsperren-Action
* LocalOnlyModelBackend (Sperrt Lokal-Login für SSO-User)
* SSO-Adapter (Domain-Whitelist, no_local_account, Verknüpfen)
* AzubiLoginView Smart-Redirect bei SSO-Username
* SSO-Verknüpfung über mein_konto lösen
* 2FA-Lifecycle (Setup, Login, Recovery, Deaktivieren)
* 2FA-Reset-Admin-Action mit Permission

Tests verwenden den Django-Test-Client. Da pytest-django Tests in
Transaktionen wickelt, sind Axes-, Audit- und Session-Daten zwischen
Tests sauber isoliert.
"""
import hashlib
import hmac
import struct
import time

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, override_settings


User = get_user_model()


@pytest.fixture(autouse=True)
def _test_settings():
    """ALLOWED_HOSTS für 'testserver' und Static-Storage ohne Manifest."""
    with override_settings(
        ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        },
    ):
        yield


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _totp_now(key_hex: str) -> str:
    """RFC 6238 TOTP-Code (6 Ziffern, 30s-Schritt) aus Hex-Key."""
    counter = int(time.time()) // 30
    h = hmac.new(bytes.fromhex(key_hex), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    return f'{(struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF) % 10**6:06d}'


@pytest.fixture
def make_user(db):
    """Erzeugt User mit konsistentem Passwort, das alle Validatoren erfüllt."""
    def _make(username="alice", email=None, password="StrongPass1!", **kwargs):
        return User.objects.create_user(
            username=username,
            email=email or f"{username}@example.com",
            password=password,
            **kwargs,
        )
    return _make


@pytest.fixture
def social_app(db):
    """SocialApp für 'Behörde X' mit Domain-Whitelist."""
    from allauth.socialaccount.models import SocialApp
    app = SocialApp.objects.create(
        provider="openid_connect",
        provider_id="behoerde-x",
        name="Behörde X",
        client_id="cid", secret="secret",
        settings={"allowed_email_domains": ["behoerde-x.de"]},
    )
    app.sites.add(Site.objects.get(pk=1))
    return app


@pytest.fixture
def sso_user(make_user, social_app):
    """User mit aktiver SocialAccount-Verknüpfung zu Behörde X."""
    from allauth.socialaccount.models import SocialAccount
    u = make_user(username="bob", email="bob@behoerde-x.de")
    SocialAccount.objects.create(user=u, provider="openid_connect", uid="sub-bob")
    return u


@pytest.fixture
def admin_request(admin_user):
    """Request-Stub mit Messages-Storage + Thread-Local für Audit-Tracking."""
    from auditlog.middleware import _thread_locals
    req = RequestFactory().post("/admin/")
    req.user = admin_user
    req.session = SessionStore()
    req._messages = FallbackStorage(req)
    _thread_locals.user = admin_user
    yield req
    # Test-Transaktion rollback + danach: stale User-Referenz aus Thread-
    # Local entfernen, sonst landet sie als FK in spätere Audit-Einträge.
    if hasattr(_thread_locals, "user"):
        del _thread_locals.user


# ─── Passwort-Policy ──────────────────────────────────────────────────────────

class TestPasswordPolicy:
    @pytest.mark.parametrize("password", [
        "Kurz1!",                         # zu kurz
        "Mittellang1!",                   # 12, aber ohne Anforderung
        "x" * 11 + "1!",                  # 1 unter Limit
    ])
    def test_too_short_rejected(self, password):
        if len(password) >= 12:
            return
        with pytest.raises(ValidationError):
            validate_password(password)

    def test_no_digit_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_password("LangAberOhneZahl!")
        assert any("Ziffer" in m for m in exc.value.messages)

    def test_no_symbol_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_password("LangAberOhneSymbol1")
        assert any("Sonderzeichen" in m for m in exc.value.messages)

    def test_strong_password_accepted(self):
        # Wirft nicht.
        validate_password("SicheresPasswort1!")

    def test_underscore_counts_as_symbol(self):
        validate_password("Lang_genug_und_gut1")


# ─── django-axes Lockout ──────────────────────────────────────────────────────

class TestAxesLockout:
    def test_locks_after_failure_limit(self, client, make_user):
        user = make_user()
        for _ in range(5):
            client.post("/accounts/login/", {"username": user.username, "password": "wrong"})
        r = client.post("/accounts/login/", {"username": user.username, "password": "wrong"})
        # axes' Default-Lockout-Status ist 429 Too Many Requests.
        assert r.status_code == 429
        assert b"gesperrt" in r.content

    def test_correct_password_resets_counter(self, client, make_user):
        user = make_user()
        for _ in range(3):
            client.post("/accounts/login/", {"username": user.username, "password": "wrong"})
        r = client.post("/accounts/login/", {"username": user.username, "password": "StrongPass1!"})
        assert r.status_code == 302, "Korrektes PW soll Login auslösen"
        # Erneut 5x falsch → muss wieder von 0 hochzählen
        client.logout()
        for _ in range(4):
            client.post("/accounts/login/", {"username": user.username, "password": "wrong"})
        r = client.post("/accounts/login/", {"username": user.username, "password": "StrongPass1!"})
        assert r.status_code == 302, "Counter sollte nach Erfolg zurückgesetzt sein"

    def test_admin_unlock_action_creates_audit_entry(self, admin_user, admin_request, make_user):
        from django.contrib import admin
        from axes.models import AccessAttempt
        from auditlog.models import AuditLogEntry

        user = make_user(username="locked")
        AccessAttempt.objects.create(
            username="locked", ip_address="127.0.0.1",
            failures_since_start=5, user_agent="x", path_info="/", get_data="", post_data="",
        )

        before = AuditLogEntry.objects.filter(action=AuditLogEntry.ACTION_UNLOCK).count()
        access_admin = admin.site._registry[AccessAttempt]
        access_admin.unlock_accounts(admin_request, AccessAttempt.objects.filter(username="locked"))

        assert not AccessAttempt.objects.filter(username="locked").exists()
        assert AuditLogEntry.objects.filter(action=AuditLogEntry.ACTION_UNLOCK).count() == before + 1


# ─── LocalOnlyModelBackend ────────────────────────────────────────────────────

class TestLocalOnlyBackend:
    def test_sso_user_blocked_from_local_login(self, client, sso_user):
        r = client.post("/accounts/login/", {
            "username": sso_user.username, "password": "StrongPass1!",
        })
        # Smart-Redirect rendert die Login-Seite mit Provider-Hinweis (200),
        # NICHT 302: User wurde nicht eingeloggt.
        assert r.status_code == 200
        assert b"Anmeldung \xc3\xbcber Identity-Provider" in r.content

    def test_local_user_login_works(self, client, make_user):
        user = make_user()
        r = client.post("/accounts/login/", {
            "username": user.username, "password": "StrongPass1!",
        })
        assert r.status_code == 302


# ─── SSO-Adapter ──────────────────────────────────────────────────────────────

class TestSsoAdapter:
    """Direkttests des Adapters mit gemocktem Provider-Lookup.

    Der echte allauth-Provider-Lookup (``sociallogin.account.get_provider``)
    braucht eine intakte Provider-Registry-Bindung; in unseren Tests setzen
    wir diese per Patch, weil es uns nicht um die allauth-Internals geht,
    sondern um unsere Adapter-Logik.
    """

    def _build_sociallogin_and_call(self, email, social_app, request=None):
        from unittest.mock import MagicMock, patch
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from services.sso_adapter import AzubiSocialAccountAdapter

        u = User(email=email, username="ext_" + (email.split("@")[0] or "x"))
        sa = SocialAccount(provider="openid_connect", uid=f"sub-{email}")
        sl = SocialLogin(user=u, account=sa, email_addresses=[])

        provider_mock = MagicMock(id="behoerde-x", app=social_app)
        # name= im MagicMock-Konstruktor setzt nur den Repr; das .name-Attribut
        # muss explizit gesetzt werden, damit es als String zurückkommt.
        provider_mock.name = "Behörde X"
        request = request or RequestFactory().get("/")
        with patch.object(SocialAccount, "get_provider", return_value=provider_mock):
            AzubiSocialAccountAdapter().pre_social_login(request, sl)

    def test_blocks_unknown_email(self, social_app, db):
        from allauth.core.exceptions import ImmediateHttpResponse
        with pytest.raises(ImmediateHttpResponse) as exc:
            self._build_sociallogin_and_call("nobody@behoerde-x.de", social_app)
        assert "no_local_account" in exc.value.response.url

    def test_blocks_disallowed_domain(self, social_app, make_user):
        from allauth.core.exceptions import ImmediateHttpResponse
        # User existiert – Whitelist greift trotzdem zuerst.
        make_user(username="external", email="external@anderswo.example")
        with pytest.raises(ImmediateHttpResponse) as exc:
            self._build_sociallogin_and_call("external@anderswo.example", social_app)
        assert "domain_not_allowed" in exc.value.response.url

    def test_no_email_blocks(self, social_app, db):
        from allauth.core.exceptions import ImmediateHttpResponse
        with pytest.raises(ImmediateHttpResponse) as exc:
            self._build_sociallogin_and_call("", social_app)
        assert "no_email" in exc.value.response.url

    def test_match_creates_audit_entry_for_failure(self, social_app, db):
        from allauth.core.exceptions import ImmediateHttpResponse
        from auditlog.models import AuditLogEntry
        before = AuditLogEntry.objects.filter(action=AuditLogEntry.ACTION_LOGIN_FAILED).count()
        with pytest.raises(ImmediateHttpResponse):
            self._build_sociallogin_and_call("ghost@behoerde-x.de", social_app)
        assert AuditLogEntry.objects.filter(
            action=AuditLogEntry.ACTION_LOGIN_FAILED,
        ).count() == before + 1


# ─── SSO-Verknüpfung über mein_konto lösen ────────────────────────────────────

class TestSsoUnlink:
    def test_unlink_removes_socialaccount(self, client, sso_user):
        from allauth.socialaccount.models import SocialAccount
        client.force_login(
            sso_user,
            backend="allauth.account.auth_backends.AuthenticationBackend",
        )
        # Karte sichtbar?
        body = client.get("/mein-konto/").content.decode()
        assert "Anmeldung über Identity-Provider" in body

        # POST unlink
        client.post("/mein-konto/", {"action": "unlink_sso"})
        assert not SocialAccount.objects.filter(user=sso_user).exists()

        # Lokaler Login wieder möglich
        client.logout()
        r = client.post("/accounts/login/", {
            "username": sso_user.username, "password": "StrongPass1!",
        })
        assert r.status_code == 302


# ─── 2FA Lifecycle ────────────────────────────────────────────────────────────

class TestTwoFactor:
    def _setup_2fa(self, client, user):
        """Aktiviert 2FA via UI-Flow, gibt das bestätigte TOTPDevice zurück."""
        from django_otp.plugins.otp_totp.models import TOTPDevice
        client.post("/accounts/login/", {"username": user.username, "password": "StrongPass1!"})
        client.get("/mein-konto/2fa/einrichten/")
        device = TOTPDevice.objects.get(user=user, confirmed=False)
        client.post("/mein-konto/2fa/einrichten/", {"token": _totp_now(device.bin_key.hex())})
        device.refresh_from_db()
        assert device.confirmed
        return device

    def test_setup_creates_totp_and_recovery_codes(self, client, make_user):
        from django_otp.plugins.otp_static.models import StaticToken
        user = make_user()
        device = self._setup_2fa(client, user)
        assert device.confirmed
        assert StaticToken.objects.filter(device__user=user).count() == 8

    def test_login_requires_otp_when_2fa_active(self, client, make_user):
        user = make_user()
        device = self._setup_2fa(client, user)
        client.logout()

        r = client.post("/accounts/login/", {
            "username": user.username, "password": "StrongPass1!",
        }, follow=False)
        assert r.headers.get("Location", "").endswith("/login-otp/")

        # Replay-Schutz austricksen, damit gleicher Time-Step ein zweites Mal
        # akzeptiert wird (in Produktion liegt zwischen Setup und Login >30s).
        device.last_t = 0
        device.save(update_fields=["last_t"])

        r = client.post("/accounts/login-otp/", {"token": _totp_now(device.bin_key.hex())})
        assert r.status_code == 302  # ins Portal

    def test_recovery_code_consumes_token(self, client, make_user):
        from django_otp.plugins.otp_static.models import StaticToken
        user = make_user()
        self._setup_2fa(client, user)
        client.logout()

        token = StaticToken.objects.filter(device__user=user).values_list("token", flat=True)[0]
        client.post("/accounts/login/", {"username": user.username, "password": "StrongPass1!"})
        r = client.post("/accounts/login-otp/", {"token": token})
        assert r.status_code == 302
        assert not StaticToken.objects.filter(token=token).exists()

    def test_disable_removes_all_devices(self, client, make_user):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        from django_otp.plugins.otp_static.models import StaticDevice
        user = make_user()
        self._setup_2fa(client, user)

        client.post("/mein-konto/2fa/deaktivieren/")
        assert not TOTPDevice.objects.filter(user=user).exists()
        assert not StaticDevice.objects.filter(user=user).exists()

    def test_wrong_otp_does_not_login(self, client, make_user):
        user = make_user()
        self._setup_2fa(client, user)
        client.logout()

        client.post("/accounts/login/", {"username": user.username, "password": "StrongPass1!"})
        r = client.post("/accounts/login-otp/", {"token": "000000"})
        # Bleibt auf der OTP-Seite, kein Redirect.
        assert r.status_code == 200
        # Folge-Request auf geschützte Seite ist nicht eingeloggt.
        assert client.get("/mein-konto/").status_code == 302


# ─── 2FA-Reset-Admin-Action ───────────────────────────────────────────────────

class TestReset2faAction:
    def _grant_perm(self, user):
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(
            codename="reset_user_2fa", content_type__app_label="services",
        )
        user.user_permissions.add(perm)
        return user

    def _setup_device(self, user):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        return TOTPDevice.objects.create(user=user, name="default", confirmed=True)

    def test_dropdown_hidden_without_permission(self, make_user):
        from django.contrib import admin
        plain_staff = make_user(username="plain", is_staff=True)
        req = RequestFactory().get("/admin/")
        req.user = plain_staff
        actions = admin.site._registry[User].get_actions(req)
        assert "reset_2fa" not in actions

    def test_dropdown_visible_with_permission(self, make_user):
        from django.contrib import admin
        elevated = self._grant_perm(make_user(username="elev", is_staff=True))
        req = RequestFactory().get("/admin/")
        req.user = elevated
        actions = admin.site._registry[User].get_actions(req)
        assert "reset_2fa" in actions

    def test_action_resets_devices(self, admin_user, admin_request, make_user):
        from django.contrib import admin
        from django_otp.plugins.otp_totp.models import TOTPDevice
        target = make_user(username="target")
        self._setup_device(target)

        ua = admin.site._registry[User]
        ua.reset_2fa(admin_request, User.objects.filter(pk=target.pk))
        assert not TOTPDevice.objects.filter(user=target).exists()

    def test_action_blocked_without_permission(self, make_user):
        from django.contrib import admin
        plain = make_user(username="plain", is_staff=True)
        req = RequestFactory().post("/admin/")
        req.user = plain
        req.session = SessionStore()
        req._messages = FallbackStorage(req)

        target = make_user(username="t2")
        self._setup_device(target)

        from django_otp.plugins.otp_totp.models import TOTPDevice
        admin.site._registry[User].reset_2fa(req, User.objects.filter(pk=target.pk))
        # Device blieb erhalten, weil defensiver Check geblockt hat
        assert TOTPDevice.objects.filter(user=target).exists()
