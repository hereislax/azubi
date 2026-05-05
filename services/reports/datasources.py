# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""DataSource-Registry für den Query-Builder.

Eine ``DataSource`` beschreibt ein freigegebenes Modell und welche Felder
darauf abfragbar sind. Felder werden als Pfad mit Doppel-Underscore-Notation
(Django-ORM-Style) angegeben (z.B. ``course__job_profile__description``).

**Sicherheitsmodell**: Nur Felder aus ``available_fields`` sind erlaubt.
Die Engine lehnt jeden Zugriff ab, der nicht in der Whitelist steht.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Feld-Typen — bestimmen Filter-Operatoren und Spalten-Formatierung
FIELD_TYPES = ('str', 'int', 'float', 'pct', 'date', 'datetime', 'bool', 'choice')


@dataclass
class DataField:
    """Ein abfragbares Feld einer DataSource.

    Attribute:
        path:    ORM-Pfad mit Doppel-Underscore (``course__job_profile__description``)
        label:   Anzeigename
        type:    Feld-Typ aus ``FIELD_TYPES``
        choices: Bei type='choice' Liste von (value, label)-Tupeln
    """
    path:    str
    label:   str
    type:    str = 'str'
    choices: list[tuple[str, str]] | None = None


@dataclass
class DataSource:
    """Eine freigegebene Datenquelle für den Query-Builder.

    Attribute:
        key:               URL-/Form-sicherer Schlüssel
        label:             Anzeigename
        model_path:        ``app.Model``
        available_fields:  Liste ``DataField``-Instanzen
        default_select:    Spalten-Pfade, die im Builder default vorausgewählt sind
    """
    key:              str
    label:            str
    model_path:       str
    available_fields: list[DataField] = field(default_factory=list)
    default_select:   list[str] = field(default_factory=list)

    def field(self, path: str) -> DataField | None:
        for f in self.available_fields:
            if f.path == path:
                return f
        return None

    def get_model(self):
        from django.apps import apps
        app_label, model_name = self.model_path.split('.')
        return apps.get_model(app_label, model_name)


# ── Registry ────────────────────────────────────────────────────────────────

_DATASOURCES: dict[str, DataSource] = {}


def register_datasource(ds: DataSource):
    if ds.key in _DATASOURCES:
        raise ValueError(f'DataSource „{ds.key}" doppelt registriert.')
    _DATASOURCES[ds.key] = ds
    return ds


def all_datasources() -> list[DataSource]:
    return sorted(_DATASOURCES.values(), key=lambda d: d.label)


def get_datasource(key: str) -> DataSource | None:
    return _DATASOURCES.get(key)


# ── Konkrete DataSources ────────────────────────────────────────────────────
# Bewusst konservative Whitelist — pro neue Anforderung Felder hier ergänzen,
# nicht im Frontend. So bleibt klar, was abgefragt werden darf.

register_datasource(DataSource(
    key='students',
    label='Nachwuchskräfte',
    model_path='student.Student',
    default_select=['first_name', 'last_name', 'course__title'],
    available_fields=[
        DataField('id',                              'ID'),
        DataField('first_name',                      'Vorname'),
        DataField('last_name',                       'Nachname'),
        DataField('email_id',                        'E-Mail'),
        DataField('phone_number',                    'Telefon'),
        DataField('birthday',                        'Geburtstag', 'date'),
        DataField('course__title',                   'Kurs'),
        DataField('course__start_date',              'Kursbeginn', 'date'),
        DataField('course__end_date',                'Kursende', 'date'),
        DataField('course__job_profile__description', 'Berufsbild'),
        DataField('course__job_profile__career__description', 'Laufbahn'),
        DataField('status__description',             'Status'),
        DataField('employment__description',         'Beschäftigung'),
        DataField('gender__description',             'Geschlecht'),
        DataField('anonymized_at',                   'Anonymisiert am', 'datetime'),
        DataField('absence_state__traffic_light',    'Abwesenheits-Ampel', 'choice',
                  choices=[('green', 'Grün'), ('yellow', 'Gelb'),
                           ('red', 'Rot'), ('unknown', 'Unbekannt')]),
    ],
))

register_datasource(DataSource(
    key='assignments',
    label='Praktikumseinsätze',
    model_path='course.InternshipAssignment',
    default_select=['student__first_name', 'student__last_name', 'unit__name', 'start_date', 'end_date'],
    available_fields=[
        DataField('id',                                'ID'),
        DataField('student__first_name',               'Azubi-Vorname'),
        DataField('student__last_name',                'Azubi-Nachname'),
        DataField('student__course__title',            'Kurs'),
        DataField('student__course__job_profile__description', 'Berufsbild'),
        DataField('unit__name',                        'Organisationseinheit'),
        DataField('unit__parent__name',                'Übergeordnete Einheit'),
        DataField('location__name',                    'Standort'),
        DataField('instructor__first_name',            'Praxistutor-Vorname'),
        DataField('instructor__last_name',             'Praxistutor-Nachname'),
        DataField('start_date',                        'Beginn', 'date'),
        DataField('end_date',                          'Ende', 'date'),
        DataField('status',                            'Status', 'choice',
                  choices=[('pending', 'Ausstehend'), ('approved', 'Genehmigt'), ('rejected', 'Abgelehnt')]),
        DataField('schedule_block__name',              'Praxisblock'),
        DataField('created_by__username',              'Angelegt von'),
        DataField('station_feedback_submitted',        'Stationsbewertung abgegeben', 'bool'),
    ],
))

register_datasource(DataSource(
    key='assessments',
    label='Stationsbeurteilungen',
    model_path='assessment.Assessment',
    default_select=['assignment__student__last_name', 'assignment__unit__name', 'status', 'submitted_at'],
    available_fields=[
        DataField('id',                                          'ID'),
        DataField('assignment__student__first_name',             'Azubi-Vorname'),
        DataField('assignment__student__last_name',              'Azubi-Nachname'),
        DataField('assignment__student__course__title',          'Kurs'),
        DataField('assignment__student__course__job_profile__description', 'Berufsbild'),
        DataField('assignment__unit__name',                      'Einheit'),
        DataField('assignment__instructor__first_name',          'Tutor-Vorname'),
        DataField('assignment__instructor__last_name',           'Tutor-Nachname'),
        DataField('assignment__end_date',                        'Einsatzende', 'date'),
        DataField('status',                                      'Status', 'choice',
                  choices=[('pending', 'Ausstehend'), ('submitted', 'Eingereicht'), ('confirmed', 'Bestätigt')]),
        DataField('submitted_at',                                'Eingereicht am', 'datetime'),
        DataField('confirmed_at',                                'Bestätigt am', 'datetime'),
        DataField('reminder_count',                              'Anzahl Erinnerungen', 'int'),
        DataField('template__name',                              'Vorlage'),
        DataField('assessor_name',                               'Beurteilende(r)'),
    ],
))

register_datasource(DataSource(
    key='vacation_requests',
    label='Urlaubsanträge',
    model_path='absence.VacationRequest',
    default_select=['student__last_name', 'start_date', 'end_date', 'status'],
    available_fields=[
        DataField('id',                                  'ID'),
        DataField('student__first_name',                 'Vorname'),
        DataField('student__last_name',                  'Nachname'),
        DataField('student__course__title',              'Kurs'),
        DataField('student__course__job_profile__description', 'Berufsbild'),
        DataField('start_date',                          'Von', 'date'),
        DataField('end_date',                            'Bis', 'date'),
        DataField('status',                              'Status'),
        DataField('working_days',                        'Arbeitstage', 'int'),
        DataField('is_cancellation',                     'Stornoantrag', 'bool'),
        DataField('submitted_via_portal',                'Über Portal', 'bool'),
        DataField('created_at',                          'Erstellt am', 'datetime'),
    ],
))

register_datasource(DataSource(
    key='study_day_requests',
    label='Lerntag-Anträge',
    model_path='studyday.StudyDayRequest',
    default_select=['student__last_name', 'date', 'request_type', 'status'],
    available_fields=[
        DataField('id',                                  'ID'),
        DataField('student__first_name',                 'Vorname'),
        DataField('student__last_name',                  'Nachname'),
        DataField('student__course__title',              'Kurs'),
        DataField('date',                                'Datum von', 'date'),
        DataField('date_end',                            'Datum bis', 'date'),
        DataField('request_type',                        'Art'),
        DataField('status',                              'Status'),
        DataField('created_at',                          'Beantragt am', 'datetime'),
        DataField('approved_at',                         'Entschieden am', 'datetime'),
    ],
))

register_datasource(DataSource(
    key='inventory_issuances',
    label='Inventar-Ausgaben',
    model_path='inventory.InventoryIssuance',
    default_select=['student__last_name', 'item__name', 'issued_at', 'returned_at'],
    available_fields=[
        DataField('id',                                  'ID'),
        DataField('student__first_name',                 'Azubi-Vorname'),
        DataField('student__last_name',                  'Azubi-Nachname'),
        DataField('item__name',                          'Gegenstand'),
        DataField('item__category__name',                'Kategorie'),
        DataField('item__serial_number',                 'Seriennummer'),
        DataField('item__status',                        'Item-Status'),
        DataField('issued_at',                           'Ausgegeben am', 'datetime'),
        DataField('returned_at',                         'Zurückgegeben am', 'datetime'),
        DataField('issued_by__username',                 'Ausgegeben von'),
    ],
))


# ── Operatoren ──────────────────────────────────────────────────────────────

OPERATORS_BY_TYPE: dict[str, list[tuple[str, str]]] = {
    'str':      [('icontains', 'enthält'), ('exact', 'ist gleich'),
                 ('startswith', 'beginnt mit'), ('isnull', 'ist leer')],
    'int':      [('exact', '='), ('gt', '>'), ('gte', '≥'), ('lt', '<'), ('lte', '≤'),
                 ('isnull', 'ist leer')],
    'float':    [('exact', '='), ('gt', '>'), ('gte', '≥'), ('lt', '<'), ('lte', '≤')],
    'pct':      [('gte', '≥'), ('lte', '≤'), ('exact', '=')],
    'date':     [('exact', 'am'), ('gte', 'ab'), ('lte', 'bis'),
                 ('isnull', 'ist leer'), ('not_isnull', 'ist gesetzt')],
    'datetime': [('date__gte', 'ab Datum'), ('date__lte', 'bis Datum'),
                 ('isnull', 'ist leer'), ('not_isnull', 'ist gesetzt')],
    'bool':     [('exact', 'ist')],
    'choice':   [('exact', 'ist'), ('in', 'ist eines von')],
}


# ── Aggregationen ───────────────────────────────────────────────────────────

AGGREGATIONS: list[tuple[str, str]] = [
    ('count',  'Anzahl'),
    ('sum',    'Summe'),
    ('avg',    'Durchschnitt'),
    ('min',    'Minimum'),
    ('max',    'Maximum'),
]
