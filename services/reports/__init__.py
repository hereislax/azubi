# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Reporting-Architektur.

Reports sind im Code als Klassen definiert (``BaseReport``-Ableitungen).
Power-User können im Frontend Filter + Spalten anpassen und als „Sichten"
(``SavedReportView``) speichern, Export erfolgt als XLSX/CSV.

Zugriff: nur Ausbildungsleitung und Ausbildungsreferat.
"""
from . import base, registry, exports  # noqa: F401
from . import operational  # registriert die Pilot-Reports beim Import
from . import trends        # noqa
from . import inventory     # noqa
from . import compliance    # noqa

__all__ = ['base', 'registry', 'exports']
