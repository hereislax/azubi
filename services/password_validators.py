# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Passwort-Policy für lokale Konten.

Wird über ``AUTH_PASSWORD_VALIDATORS`` eingehängt und greift sowohl beim
Anlegen eines Kontos als auch beim Zurücksetzen über den E-Mail-Reset-Flow.
"""
import re

from django.core.exceptions import ValidationError


class SymbolAndDigitValidator:
    """Verlangt mindestens eine Ziffer und mindestens ein Sonderzeichen.

    Sonderzeichen = alles, was kein lateinischer Buchstabe und keine Ziffer
    ist. Umlaute zählen unter dieser Definition zusätzlich als Sonderzeichen –
    in der Praxis irrelevant, da das nur bedeutet, dass Passwörter mit
    Umlauten den Sonderzeichen-Check ohnehin erfüllen.
    """

    DIGIT_RE = re.compile(r'[0-9]')
    SYMBOL_RE = re.compile(r'[^A-Za-z0-9]')

    def validate(self, password, user=None):
        errors = []
        if not self.DIGIT_RE.search(password):
            errors.append(ValidationError(
                'Das Passwort muss mindestens eine Ziffer enthalten.',
                code='password_no_digit',
            ))
        if not self.SYMBOL_RE.search(password):
            errors.append(ValidationError(
                'Das Passwort muss mindestens ein Sonderzeichen enthalten '
                '(z. B. ! ? & % @ #).',
                code='password_no_symbol',
            ))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            'Das Passwort muss mindestens eine Ziffer und mindestens ein '
            'Sonderzeichen (z. B. ! ? & % @ #) enthalten.'
        )
