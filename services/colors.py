# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Zentrale Farb-Definitionen und Helper.

Quelle der Wahrheit für die offizielle Farbpalette der Bundesregierung
(https://styleguide.bundesregierung.gov.de/sg-de/basiselemente/farben).
Wird in Kalendern, Diagrammen und der Erscheinungsbild-Konfiguration genutzt.

Modelle nutzen Bootstrap-Klassennamen (`primary`, `success`, ...) als Color-Choice,
damit Badges (`bg-{{color}}`) sauber funktionieren. Für Kalender-Balken brauchen
wir aber Hex-Werte. `bootstrap_to_hex()` bildet die Klassen auf die in
`SiteConfiguration` konfigurierten Brand-Farben ab.
"""
from __future__ import annotations

# ── Stilguide der Bundesregierung: Basisfarben ────────────────────────────────
# Reihenfolge entspricht dem Farbkreis (warm → kalt → neutral).

BUNDESFARBEN: list[tuple[str, str]] = [
    ('Violett',      '#5F316E'),
    ('Dunkelrot',    '#780F2D'),
    ('Rot',          '#C0003C'),
    ('Orange',       '#CD5038'),
    ('Hellorange',   '#F7BB3D'),
    ('Gelb',         '#F9E03A'),
    ('Hellgrün',     '#C1CA31'),
    ('Oliv',         '#597C39'),
    ('Dunkelgrün',   '#005C45'),
    ('Grün',         '#00854A'),
    ('Türkis',       '#00818B'),
    ('Hellblau',     '#80CDEC'),
    ('Blau',         '#0077B6'),
    ('Petrol',       '#007194'),
    ('Dunkelblau',   '#004B76'),
    ('Dunkelgrau',   '#576164'),
    ('Hellgrau',     '#BEC5C9'),
]

# Reine Hex-Liste für deterministische Farbvergabe (Kalenderbalken, Diagramme).
# Reihenfolge so gewählt, dass aufeinanderfolgende Indizes maximal kontrastieren.
BUNDESFARBEN_PALETTE: list[str] = [
    '#0077B6',  # Blau
    '#C0003C',  # Rot
    '#00854A',  # Grün
    '#CD5038',  # Orange
    '#5F316E',  # Violett
    '#00818B',  # Türkis
    '#F7BB3D',  # Hellorange
    '#004B76',  # Dunkelblau
    '#597C39',  # Oliv
    '#780F2D',  # Dunkelrot
    '#007194',  # Petrol
    '#005C45',  # Dunkelgrün
    '#C1CA31',  # Hellgrün
    '#80CDEC',  # Hellblau
    '#576164',  # Dunkelgrau
    '#F9E03A',  # Gelb
    '#BEC5C9',  # Hellgrau
]


# Lookup nach deutschem Namen – für semantische Verwendungen (z. B. „Krankmeldung = Rot")
BUNDESFARBEN_BY_NAME: dict[str, str] = {name: hex_value for name, hex_value in BUNDESFARBEN}


def pick_color(key, palette: list[str] | None = None) -> str:
    """
    Wählt deterministisch eine Farbe aus der Palette anhand eines Schlüssels.
    Gleicher Schlüssel ergibt immer dieselbe Farbe – stabil über Requests hinweg.
    """
    pal = palette or BUNDESFARBEN_PALETTE
    return pal[hash(str(key)) % len(pal)]


# Fallback-Hex (Bootstrap 5 Defaults), wenn SiteConfiguration nicht erreichbar
_BOOTSTRAP_FALLBACK = {
    'primary':   '#0d6efd',
    'secondary': '#6c757d',
    'success':   '#198754',
    'danger':    '#dc3545',
    'warning':   '#ffc107',
    'info':      '#0dcaf0',
    'dark':      '#212529',
    'light':     '#f8f9fa',
}


def bootstrap_to_hex(name: str | None, default: str = '#6c757d') -> str:
    """
    Wandelt einen Bootstrap-Color-Klassennamen (z. B. `primary`, `danger`)
    in den passenden Hex-Wert um.

    Liest die konfigurierten Brand-Farben aus `SiteConfiguration` und fällt
    auf Bootstrap-Defaults zurück, wenn diese nicht gesetzt sind oder ein
    nicht zugeordneter Name übergeben wird (z. B. `dark`).
    """
    if not name:
        return default

    try:
        from services.models import SiteConfiguration
        config = SiteConfiguration.get()
        mapping = {
            'primary':   config.brand_primary_color,
            'secondary': config.brand_secondary_color,
            'success':   config.brand_success_color,
            'danger':    config.brand_danger_color,
            'warning':   config.brand_warning_color,
            'info':      config.brand_info_color,
        }
        if name in mapping and mapping[name]:
            return mapping[name]
    except Exception:
        pass

    return _BOOTSTRAP_FALLBACK.get(name, default)