# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Registry für alle Reports. Pro Report-Klasse einmalig ``@register`` aufrufen."""
from __future__ import annotations

from .base import BaseReport


_REPORTS: dict[str, type[BaseReport]] = {}


def register(cls: type[BaseReport]) -> type[BaseReport]:
    """Decorator: registriert eine Report-Klasse unter ihrem ``slug``."""
    if not getattr(cls, 'slug', None):
        raise ValueError(f'{cls.__name__}: slug fehlt.')
    if cls.slug in _REPORTS:
        raise ValueError(f'Report-Slug „{cls.slug}" doppelt vergeben '
                         f'({_REPORTS[cls.slug].__name__} vs. {cls.__name__}).')
    _REPORTS[cls.slug] = cls
    return cls


def all_reports() -> list[type[BaseReport]]:
    """Alle registrierten Reports, alphabetisch nach Kategorie + Name."""
    return sorted(_REPORTS.values(), key=lambda c: (c.category, c.name))


def get_report(slug: str) -> type[BaseReport] | None:
    return _REPORTS.get(slug)
