# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Eigene Authentication-Backends.

``LocalOnlyModelBackend`` ersetzt das Django-Default-ModelBackend und
verhindert, dass Benutzer mit verknüpfter externer Identität (allauth-
SocialAccount) sich über Username + Passwort anmelden. Diese User sollen
ausschließlich über ihre Behörden-IdP authentifiziert werden.

Der Notfall-Admin (lokaler Superuser ohne SSO-Verknüpfung) bleibt von
dieser Regel unberührt.
"""
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied


class LocalOnlyModelBackend(ModelBackend):
    """ModelBackend, das User mit verknüpfter externer Identität ausschließt.

    PermissionDenied wird absichtlich geworfen statt ``False`` zurückzugeben:
    Django's ``authenticate()`` bricht beim PermissionDenied die gesamte
    Backend-Kette ab. Andernfalls würde z.B. das allauth-AuthenticationBackend
    danach durchlaufen und den SSO-User trotzdem akzeptieren.
    """

    def user_can_authenticate(self, user):
        if not super().user_can_authenticate(user):
            return False
        # Lazy-Import vermeidet App-Loading-Probleme bei Django-Start.
        from allauth.socialaccount.models import SocialAccount
        if SocialAccount.objects.filter(user=user).exists():
            raise PermissionDenied(
                'Dieser Benutzer ist mit einem Identity-Provider verknüpft '
                'und muss sich darüber anmelden.'
            )
        return True
