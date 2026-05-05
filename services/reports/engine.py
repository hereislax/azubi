# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Engine: führt eine ``CustomReport.definition`` sicher als Django-ORM-Query aus.

**Sicherheits-Modell**: jeder Feld-Pfad und jeder Operator muss im
``DataSource.available_fields`` bzw. ``OPERATORS_BY_TYPE`` der DataSource
freigegeben sein. Unbekannte Pfade/Operatoren werden ignoriert (silent skip)
oder werfen ``InvalidReportDefinition``.
"""
from __future__ import annotations

from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Max, Min, Q, Sum

from .base import Column
from .datasources import (
    AGGREGATIONS, OPERATORS_BY_TYPE, DataSource,
    get_datasource,
)


class InvalidReportDefinition(ValidationError):
    pass


_AGG_FUNCS = {'count': Count, 'sum': Sum, 'avg': Avg, 'min': Min, 'max': Max}


def _coerce_value(raw, field_type: str):
    if raw is None or raw == '':
        return None
    if field_type == 'int':
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    if field_type in ('float', 'pct'):
        try:
            return float(str(raw).replace(',', '.'))
        except (TypeError, ValueError):
            return None
    if field_type == 'date':
        if isinstance(raw, date):
            return raw
        try:
            return date.fromisoformat(str(raw))
        except ValueError:
            return None
    if field_type == 'datetime':
        if isinstance(raw, datetime):
            return raw
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None
    if field_type == 'bool':
        return str(raw).lower() in ('1', 'true', 'on', 'yes', 'ja')
    return str(raw)


def _build_filter_q(ds: DataSource, filt: dict) -> Q | None:
    """Baut ein einzelnes Q-Objekt aus einem Filter-Dict (oder None bei ungültig)."""
    path = filt.get('field')
    op   = filt.get('op', 'exact')
    raw  = filt.get('value')
    df = ds.field(path or '')
    if df is None:
        return None
    allowed_ops = {o for o, _ in OPERATORS_BY_TYPE.get(df.type, [])}
    if op not in allowed_ops:
        return None

    # Spezialfälle: isnull / not_isnull brauchen keinen Wert
    if op == 'isnull':
        return Q(**{f'{path}__isnull': True})
    if op == 'not_isnull':
        return Q(**{f'{path}__isnull': False})

    value = _coerce_value(raw, df.type)
    if value is None and df.type != 'bool':
        return None

    if op == 'in':
        # Komma-getrennte Liste
        items = [s.strip() for s in str(raw).split(',') if s.strip()]
        if not items:
            return None
        return Q(**{f'{path}__in': items})

    return Q(**{f'{path}__{op}': value})


def execute_custom_report(definition: dict, limit: int | None = 1000) -> tuple[list[Column], list[dict]]:
    """Führt eine Custom-Report-Definition aus und liefert Spalten + Zeilen.

    Bei Fehlern in der Definition (unbekannte DataSource o.ä.) wird
    ``InvalidReportDefinition`` geworfen. Einzelne ungültige Filter werden
    stillschweigend übersprungen — der Builder zeigt das im UI bereits.
    """
    ds_key = definition.get('datasource')
    ds = get_datasource(ds_key or '')
    if ds is None:
        raise InvalidReportDefinition(f'Datenquelle „{ds_key}" unbekannt.')

    select_paths   = list(definition.get('select') or [])
    group_by_paths = list(definition.get('group_by') or [])
    aggregations   = list(definition.get('aggregations') or [])
    order_by_paths = list(definition.get('order_by') or [])
    filters        = list(definition.get('filters') or [])
    eff_limit      = int(definition.get('limit') or limit or 1000)

    # Whitelist: nur Felder aus DataSource zulassen
    valid_paths = {f.path for f in ds.available_fields}
    select_paths   = [p for p in select_paths if p in valid_paths]
    group_by_paths = [p for p in group_by_paths if p in valid_paths]
    order_by_paths = [
        p for p in order_by_paths
        if p.lstrip('-') in valid_paths
        or p.lstrip('-') in {a.get('alias') or f'{a.get("op")}_{a.get("field")}' for a in aggregations}
    ]

    Model = ds.get_model()
    qs = Model.objects.all()

    # Filter
    for f in filters:
        q = _build_filter_q(ds, f)
        if q is not None:
            qs = qs.filter(q)

    # Aggregations + group_by
    if group_by_paths or aggregations:
        annotations = {}
        for agg in aggregations:
            field_path = agg.get('field')
            op = agg.get('op')
            alias = agg.get('alias') or f'{op}_{field_path}'
            if op not in _AGG_FUNCS:
                continue
            if op != 'count' and field_path not in valid_paths:
                continue
            target = field_path if (op != 'count' or field_path in valid_paths) else 'pk'
            annotations[alias] = _AGG_FUNCS[op](target)
        if not annotations:
            # ohne Aggregation gibt group_by allein keinen Sinn
            qs_values = qs.values(*group_by_paths) if group_by_paths else qs
            data = list(qs_values[:eff_limit])
            columns = _build_select_columns(ds, group_by_paths or select_paths)
            return columns, data

        qs = qs.values(*group_by_paths).annotate(**annotations)

        if order_by_paths:
            qs = qs.order_by(*order_by_paths)

        rows = list(qs[:eff_limit])
        columns = _build_select_columns(ds, group_by_paths)
        for agg in aggregations:
            op = agg.get('op')
            if op not in _AGG_FUNCS:
                continue
            alias = agg.get('alias') or f'{op}_{agg.get("field")}'
            label = _agg_label(ds, agg)
            ftype = 'int' if op == 'count' else _agg_field_type(ds, agg)
            columns.append(Column(alias, label, type=ftype, align='right', total=(op != 'avg')))
        return columns, rows

    # Detail-Liste (kein group_by)
    if not select_paths:
        select_paths = list(ds.default_select)
    if order_by_paths:
        qs = qs.order_by(*order_by_paths)

    rows = []
    for obj in qs[:eff_limit].values(*select_paths):
        rows.append(obj)
    columns = _build_select_columns(ds, select_paths)
    return columns, rows


def _build_select_columns(ds: DataSource, paths: list[str]) -> list[Column]:
    cols = []
    for p in paths:
        df = ds.field(p)
        if df is None:
            continue
        align = 'right' if df.type in ('int', 'float', 'pct') else 'left'
        cols.append(Column(p, df.label, type=df.type, align=align))
    return cols


def _agg_label(ds: DataSource, agg: dict) -> str:
    op = agg.get('op')
    field_path = agg.get('field')
    op_label = dict(AGGREGATIONS).get(op, op)
    if op == 'count' and not field_path:
        return f'{op_label}'
    df = ds.field(field_path or '')
    field_label = df.label if df else (field_path or '')
    return f'{op_label} ({field_label})'


def _agg_field_type(ds: DataSource, agg: dict) -> str:
    df = ds.field(agg.get('field') or '')
    if df is None:
        return 'float'
    return df.type if df.type in ('int', 'float', 'pct') else 'float'
