# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Basis-Klassen für Reports: Column, Filter, BaseReport.

Ein Report-Subklasse definiert:

- ``slug``, ``name``, ``category``, ``description``  (Metadaten)
- ``columns``                       (Liste von ``Column``-Instanzen)
- ``filters``                       (Liste von ``Filter``-Instanzen)
- ``get_rows(filter_values: dict)`` (liefert Liste[dict] mit Spalten-Keys)
- optional ``chart``                (Chart-Konfiguration)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable


# ── Spalten-Definition ──────────────────────────────────────────────────────

COLUMN_TYPES = ('str', 'int', 'float', 'pct', 'date', 'datetime')


@dataclass
class Column:
    """Eine Spalten-Definition eines Reports.

    Attribute:
        key:       Schlüssel im Row-Dict
        label:     Anzeigename in Tabellen-Header und Excel-Spalte
        type:      Datentyp für Formatierung/Sortierung (siehe COLUMN_TYPES)
        sortable:  In der Frontend-Tabelle sortierbar
        total:     In der Excel-Summenzeile aufsummieren (nur int/float/pct)
        link:      optionale Funktion (row) → URL für klickbare Zellen
        align:     'left' | 'right' | 'center'
        default:   Wert für Zellen, die im Row-Dict fehlen
    """
    key:      str
    label:    str
    type:     str = 'str'
    sortable: bool = True
    total:    bool = False
    link:     Callable[[dict], str] | None = None
    align:    str = 'left'
    default:  Any = ''


# ── Filter-Definitionen ─────────────────────────────────────────────────────

@dataclass
class Filter:
    """Basis-Filter. Subklassen liefern type-spezifisches Rendering."""
    key:     str
    label:   str
    default: Any = None
    help:    str = ''

    type: str = 'text'  # wird von Subklassen überschrieben

    def parse(self, raw: str | None) -> Any:
        return raw or self.default

    def widget_attrs(self) -> dict[str, str]:
        return {'type': 'text', 'class': 'kern-form-input__input'}


@dataclass
class DateRangeFilter(Filter):
    type: str = 'date_range'

    def parse(self, raw):
        # raw ist ein Tupel (start, end) oder String "yyyy-mm-dd|yyyy-mm-dd"
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            return [self._d(raw[0]), self._d(raw[1])]
        if isinstance(raw, str) and '|' in raw:
            a, b = raw.split('|', 1)
            return [self._d(a), self._d(b)]
        return [None, None]

    @staticmethod
    def _d(s):
        try:
            return date.fromisoformat(s) if s else None
        except ValueError:
            return None


@dataclass
class ChoiceFilter(Filter):
    """Filter mit fester Liste von Optionen."""
    type: str = 'choice'
    choices: list[tuple[str, str]] = field(default_factory=list)

    def parse(self, raw):
        if raw and any(raw == v for v, _ in self.choices):
            return raw
        return self.default


@dataclass
class ModelFilter(Filter):
    """Filter über alle Instanzen eines Modells (Dropdown)."""
    type: str = 'model'
    queryset_factory: Callable[[], Iterable] | None = None  # callable returning queryset
    label_field: str = 'name'
    multi: bool = False

    def parse(self, raw):
        if not raw:
            return [] if self.multi else None
        if self.multi:
            if isinstance(raw, (list, tuple)):
                return [r for r in raw if r]
            return [s for s in str(raw).split(',') if s]
        return raw


@dataclass
class BoolFilter(Filter):
    type: str = 'bool'

    def parse(self, raw):
        return raw in ('1', 'true', 'on', True)


# ── Chart-Konfiguration (optional) ──────────────────────────────────────────

@dataclass
class BarChart:
    x:     str
    y:     str
    label: str | None = None

    def to_dict(self):
        return {'type': 'bar', 'x': self.x, 'y': self.y, 'label': self.label}


@dataclass
class LineChart:
    x:     str
    y:     str
    label: str | None = None

    def to_dict(self):
        return {'type': 'line', 'x': self.x, 'y': self.y, 'label': self.label}


# ── BaseReport ──────────────────────────────────────────────────────────────

class BaseReport:
    """Basis aller Reports. In Subklassen Class-Attribute setzen + ``get_rows`` implementieren."""

    slug:        str = ''
    name:        str = ''
    category:    str = 'Allgemein'
    description: str = ''

    columns: list[Column] = []
    filters: list[Filter] = []
    chart:   Any = None  # BarChart | LineChart | None

    def get_rows(self, filter_values: dict) -> list[dict]:
        raise NotImplementedError

    def parse_filters(self, raw: dict) -> dict:
        """Parst die GET-Parameter durch alle definierten Filter."""
        out = {}
        for f in self.filters:
            raw_val = raw.get(f.key)
            if f.type == 'date_range':
                start = raw.get(f'{f.key}_start')
                end   = raw.get(f'{f.key}_end')
                out[f.key] = f.parse((start, end))
            elif isinstance(f, ModelFilter) and f.multi:
                out[f.key] = f.parse(raw.getlist(f.key) if hasattr(raw, 'getlist') else raw_val)
            else:
                out[f.key] = f.parse(raw_val)
        return out

    def visible_columns(self, only_keys: list[str] | None = None) -> list[Column]:
        """Liefert die Spalten, ggf. gefiltert auf eine vom User gewählte Auswahl."""
        if not only_keys:
            return list(self.columns)
        ordered = []
        by_key = {c.key: c for c in self.columns}
        for k in only_keys:
            if k in by_key:
                ordered.append(by_key[k])
        return ordered or list(self.columns)

    def chart_dict(self):
        return self.chart.to_dict() if self.chart else None
