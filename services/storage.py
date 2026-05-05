# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Hilfsfunktionen für die Speicherung von Datei-Uploads.

Konvention: Statt den vom Benutzer übermittelten Dateinamen direkt in
``MEDIA_ROOT`` zu speichern (was bei identischen Namen zu Konflikten
oder unvorhersehbaren Suffixen führt), erzeugen wir einen UUID-basierten
Pfad. Der Original-Dateiname wird – wo gewünscht – in einem zusätzlichen
Modell-Feld festgehalten und beim Download wieder verwendet.
"""
from __future__ import annotations

import os
import uuid

from django.utils.deconstruct import deconstructible


@deconstructible
class uuid_upload_to:
    """``upload_to``-Callable, das ``<prefix>/<uuid>.<ext>`` produziert.

    Beispiel::

        attachment = models.FileField(upload_to=uuid_upload_to('inquiries/attachments/'))

    Bei einem Upload ``Bewerbung.pdf`` wird der Pfad zu
    ``inquiries/attachments/0f7a2c4e-….pdf``. Die Endung wird beibehalten,
    damit der Browser den richtigen Content-Type erkennt; der ursprüngliche
    Dateiname soll – falls für die UI relevant – im Modell separat
    gespeichert werden.

    Implementiert als ``@deconstructible``-Klasse, damit das Objekt von
    Django-Migrationen serialisiert werden kann (eine Closure-Funktion
    funktioniert dort nicht).
    """

    def __init__(self, prefix: str):
        self.prefix = prefix.rstrip('/')

    def __call__(self, instance, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return f'{self.prefix}/{uuid.uuid4()}{ext}'

    def __eq__(self, other):
        return isinstance(other, uuid_upload_to) and other.prefix == self.prefix

    def __hash__(self):
        return hash(('uuid_upload_to', self.prefix))