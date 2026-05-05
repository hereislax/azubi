# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Stationsauslastung (Belegungsgrad pro Organisationseinheit).

Bezieht sich auf den vom Filter gewählten Stichtag (Default heute).
Auslastung = (aktive Einsätze an diesem Tag) / max_capacity * 100.
Einheiten ohne max_capacity werden übersprungen.
"""
from __future__ import annotations

from datetime import date

from ..base import BaseReport, Column, DateRangeFilter, ChoiceFilter, BarChart, Filter
from ..registry import register


@register
class StationsauslastungReport(BaseReport):
    slug        = 'stationsauslastung'
    name        = 'Stationsauslastung'
    category    = 'Operativ'
    description = ('Auslastung der Organisationseinheiten zum Stichtag. '
                   'Einheiten ohne hinterlegte Maximalkapazität werden ausgeblendet.')

    columns = [
        Column('unit',          'Einheit',         sortable=True),
        Column('parent',        'Übergeordnet',    sortable=True),
        Column('current',       'Aktuell',         type='int', align='right', total=True),
        Column('max_capacity',  'Maximum',         type='int', align='right', total=True),
        Column('utilization',   'Auslastung',      type='pct', align='right'),
        Column('status',        'Status',          align='center'),
    ]

    @property
    def filters(self):
        return [
            _StichtagFilter('stichtag', label='Stichtag', default=date.today().isoformat()),
            ChoiceFilter('only', label='Anzeige',
                         choices=[('', 'Alle Einheiten'),
                                  ('over', 'nur überlastet (≥ 100%)'),
                                  ('high', 'nur hoch ausgelastet (≥ 80%)'),
                                  ('low', 'nur unterausgelastet (≤ 50%)')],
                         default=''),
        ]

    chart = BarChart(x='unit', y='utilization', label='Auslastung (%)')

    def get_rows(self, filter_values: dict) -> list[dict]:
        from organisation.models import OrganisationalUnit
        from course.models import InternshipAssignment, ASSIGNMENT_STATUS_APPROVED

        stichtag = filter_values.get('stichtag') or date.today()
        if isinstance(stichtag, str):
            try:
                stichtag = date.fromisoformat(stichtag)
            except ValueError:
                stichtag = date.today()

        only = filter_values.get('only') or ''

        units = (
            OrganisationalUnit.objects
            .filter(max_capacity__isnull=False, is_active=True)
            .select_related('parent')
            .order_by('unit_type', 'name')
        )
        rows = []
        for u in units:
            current = (
                InternshipAssignment.objects
                .filter(unit=u, status=ASSIGNMENT_STATUS_APPROVED,
                        start_date__lte=stichtag, end_date__gte=stichtag)
                .count()
            )
            cap = u.max_capacity or 0
            util = (current / cap * 100) if cap else 0
            if only == 'over' and util < 100: continue
            if only == 'high' and util < 80:  continue
            if only == 'low'  and util > 50:  continue

            if   util >= 100: status = 'überlastet'
            elif util >= 80:  status = 'hoch'
            elif util >= 50:  status = 'mittel'
            else:             status = 'niedrig'

            rows.append({
                'unit':         u.name,
                'parent':       u.parent.name if u.parent else '—',
                'current':      current,
                'max_capacity': cap,
                'utilization':  round(util, 1),
                'status':       status,
            })
        return rows


class _StichtagFilter(Filter):
    """Einzelnes Datumsfeld als Filter — Stichtag-Variante."""
    type = 'date'

    def parse(self, raw):
        if isinstance(raw, date):
            return raw
        try:
            return date.fromisoformat(raw) if raw else date.today()
        except (ValueError, TypeError):
            return date.today()
