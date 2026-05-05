# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Template-Filter für Reporting (Dict-Lookup, Wert-Formatierung)."""
from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    """Erlaubt {{ mydict|get_item:variable_key }} im Template."""
    if d is None:
        return None
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def cell_value(row, key):
    """Liest einen Wert aus einer Report-Zeile (defensiv)."""
    if row is None:
        return ''
    try:
        return row.get(key, '')
    except AttributeError:
        return ''


@register.filter
def format_cell(value, col_type):
    """Formatiert einen Wert je Spalten-Typ für die Tabellen-Anzeige."""
    if value is None or value == '':
        return ''
    if col_type == 'date' and hasattr(value, 'strftime'):
        return value.strftime('%d.%m.%Y')
    if col_type == 'datetime' and hasattr(value, 'strftime'):
        return value.strftime('%d.%m.%Y %H:%M')
    if col_type == 'pct':
        try:
            return f'{float(value):.1f} %'.replace('.', ',')
        except (ValueError, TypeError):
            return value
    if col_type == 'float':
        try:
            return f'{float(value):.2f}'.replace('.', ',')
        except (ValueError, TypeError):
            return value
    return value


@register.filter
def is_in(value, csv_list):
    """Prüft ob value in einer komma-getrennten Liste enthalten ist."""
    if not csv_list:
        return False
    return str(value) in [s.strip() for s in str(csv_list).split(',')]
