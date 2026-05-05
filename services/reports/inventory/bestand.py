# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Inventar-Bestand pro Kategorie und Status."""
from __future__ import annotations

from ..base import BaseReport, Column, ModelFilter, BarChart
from ..registry import register


@register
class InventarBestandReport(BaseReport):
    slug        = 'inventar-bestand'
    name        = 'Inventar-Bestand'
    category    = 'Inventar'
    description = ('Bestand pro Inventar-Kategorie mit Aufteilung nach Status '
                   '(verfügbar / ausgegeben / defekt / ausgemustert).')

    columns = [
        Column('category',      'Kategorie',     sortable=True),
        Column('total',         'Gesamt',        type='int', align='right', total=True),
        Column('verfuegbar',    'Verfügbar',     type='int', align='right', total=True),
        Column('ausgegeben',    'Ausgegeben',    type='int', align='right', total=True),
        Column('defekt',        'Defekt',        type='int', align='right', total=True),
        Column('ausgemustert',  'Ausgemustert',  type='int', align='right', total=True),
        Column('utilisation',   'Nutzungsquote', type='pct', align='right'),
    ]

    @property
    def filters(self):
        from inventory.models import InventoryCategory
        return [
            ModelFilter('category', label='Kategorie', multi=False,
                        queryset_factory=lambda: InventoryCategory.objects.order_by('name')),
        ]

    chart = BarChart(x='category', y='ausgegeben', label='Ausgegebene Stücke')

    def get_rows(self, filter_values: dict) -> list[dict]:
        from inventory.models import InventoryCategory, InventoryItem

        cats = InventoryCategory.objects.order_by('name')
        cat_pk = filter_values.get('category')
        if cat_pk:
            cats = cats.filter(pk=cat_pk)

        rows = []
        for cat in cats:
            items = InventoryItem.objects.filter(category=cat)
            total = items.count()
            if not total:
                continue
            verfuegbar    = items.filter(status='verfuegbar').count()
            ausgegeben    = items.filter(status='ausgegeben').count()
            defekt        = items.filter(status='defekt').count()
            ausgemustert  = items.filter(status='ausgemustert').count()
            utilisation = round((ausgegeben / total * 100), 1) if total else 0
            rows.append({
                'category':     cat.name,
                'total':        total,
                'verfuegbar':   verfuegbar,
                'ausgegeben':   ausgegeben,
                'defekt':       defekt,
                'ausgemustert': ausgemustert,
                'utilisation':  utilisation,
            })
        return rows
