# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Zentrale Datenmodelle und Dienste: Benachrichtigungsvorlagen, Benutzerprofile, Site-Konfiguration."""

from django.db import models


# ── Benachrichtigungsvorlagen ────────────────────────────────────────────────

NOTIFICATION_KEYS = [
    ('instructor_assignment', 'Praxistutor: Nachwuchskraft zugewiesen'),
    ('instructor_confirmed',  'Bestellungsschreiben: Praxistutor bestätigt'),
    ('instructor_confirmed_coordinator', 'Praxistutor bestätigt: Information an Koordination'),
    ('chief_assignment',      'Ausbildungskoordination: Einsatz angelegt/geändert'),
    ('chief_welcome',         'Willkommen: Benutzerkonto angelegt'),
    ('reminder_start',        'Erinnerung: Einsatz beginnt in 7 Tagen'),
    ('reminder_end',          'Erinnerung: Einsatz endet in 7 Tagen'),
    ('assignment_approved',   'Rückmeldung: Einsatz angenommen'),
    ('assignment_rejected',      'Rückmeldung: Einsatz abgelehnt'),
    ('practice_grade_confirmed',   'Bewertung: Praxisabschnitt bestätigt'),
    ('proof_of_training_approved',   'Ausbildungsnachweis: Angenommen'),
    ('proof_of_training_rejected',   'Ausbildungsnachweis: Korrekturbedarf'),
    ('proof_of_training_reminder',   'Erinnerung: Ausbildungsnachweis fehlt oder nicht eingereicht'),
    ('student_portal_welcome',       'Portal-Begrüßung: Zugangsdaten Nachwuchskraft'),
    ('study_day_approved',           'Lerntag: Antrag genehmigt'),
    ('study_day_rejected',           'Lerntag: Antrag abgelehnt'),
    ('study_day_cancelled',          'Lerntag: Genehmigter Tag storniert'),
    ('vacation_approved',            'Urlaub: Antrag genehmigt'),
    ('vacation_rejected',            'Urlaub: Antrag abgelehnt'),
    ('vacation_processed',           'Urlaub: Durch Urlaubsstelle bearbeitet'),
    ('inventory_issued',             'Inventar: Gegenstand ausgegeben'),
    ('inventory_returned',           'Inventar: Gegenstand zurückgegeben'),
    ('assessment_token_sent',        'Beurteilung: Link an Praxistutoren gesendet'),
    ('assessment_reminder',          'Beurteilung: Erinnerung an Praxistutoren (Stufe 1)'),
    ('assessment_reminder_urgent',   'Beurteilung: Dringende Erinnerung an Praxistutoren (Stufe 2)'),
    ('assessment_escalation',        'Beurteilung: Eskalation an Ausbildungskoordination (Stufe 3)'),
    ('assessment_submitted',         'Beurteilung: Praxistutoren hat eingereicht'),
    ('inquiry_new',                  'Nachricht: Neue Anfrage von Nachwuchskraft'),
    ('inquiry_reply',                'Nachricht: Antwort vom Ausbildungsreferat'),
    ('document_generated',           'Dokument: Bescheinigung erstellt'),
    ('change_request_submitted',     'Änderungsantrag: Neuer Antrag eingegangen'),
    ('change_request_approved',      'Änderungsantrag: Antrag genehmigt'),
    ('change_request_rejected',      'Änderungsantrag: Antrag abgelehnt'),
    ('assignment_decision_for_office', 'Praktikumseinsatz: Entscheidung der Koordination (Info Referat)'),
]

# Verfügbare Template-Variablen je Schlüssel – wird als Hilfetext im Admin angezeigt.
NOTIFICATION_VARIABLES = {
    'instructor_confirmed': [
        ('anrede',       'Vollständige Anredezeile, z. B. „Guten Tag Max Mustermann,"'),
        ('vorname',      'Vorname des Praxistutors'),
        ('nachname',     'Nachname des Praxistutors'),
        ('einheit',      'Name der Organisationseinheit'),
        ('berufsbilder', 'Zugewiesene Berufsbilder (kommagetrennt)'),
        ('detail_url',   'Link zum Praxistutor-Profil'),
    ],
    'instructor_confirmed_coordinator': [
        ('anrede',            'Anredezeile – persönlich oder „Guten Tag," bei Funktionspostfach'),
        ('vorname',           'Vorname des Praxistutors'),
        ('nachname',          'Nachname des Praxistutors'),
        ('praxistutor_email', 'Dienstliche E-Mail des Praxistutors'),
        ('einheit',           'Name der Organisationseinheit'),
        ('berufsbilder',      'Zugewiesene Berufsbilder (kommagetrennt)'),
        ('detail_url',        'Link zum Praxistutor-Profil'),
    ],
    'instructor_assignment': [
        ('anrede',            'Vollständige Anredezeile, z. B. „Guten Tag Max Mustermann,"'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('detail_url',        'Link zur Nachwuchskraft (Studentenprofil)'),
    ],
    'chief_assignment': [
        ('anrede',            'Anredezeile – persönlich oder „Guten Tag," bei Funktionspostfach'),
        ('action',            '„angelegt" oder „geändert"'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('detail_url',        'Link zur Detailseite der Ausbildungskoordination'),
    ],
    'chief_welcome': [
        ('vorname',      'Vorname der Ausbildungskoordination'),
        ('nachname',     'Nachname der Ausbildungskoordination'),
        ('benutzername', 'Benutzername des neuen Kontos'),
        ('passwort_url', 'Link zum Setzen des Passworts'),
    ],
    'reminder_start': [
        ('anrede',           'Vollständige Anredezeile'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Name der Organisationseinheit'),
        ('von',              'Startdatum (TT.MM.JJJJ)'),
        ('bis',              'Enddatum (TT.MM.JJJJ)'),
        ('block',            'Name des Ausbildungsblocks'),
    ],
    'reminder_end': [
        ('anrede',           'Vollständige Anredezeile'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Name der Organisationseinheit'),
        ('von',              'Startdatum (TT.MM.JJJJ)'),
        ('bis',              'Enddatum (TT.MM.JJJJ)'),
        ('block',            'Name des Ausbildungsblocks'),
    ],
    'assignment_approved': [
        ('vorname',          'Vorname der anlegenden Person'),
        ('nachname',         'Nachname der anlegenden Person'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Name der Organisationseinheit'),
        ('von',              'Startdatum (TT.MM.JJJJ)'),
        ('bis',              'Enddatum (TT.MM.JJJJ)'),
        ('block',            'Name des Ausbildungsblocks'),
        ('detail_url',       'Link zum Praktikumskalender'),
    ],
    'assignment_rejected': [
        ('vorname',           'Vorname der anlegenden Person'),
        ('nachname',          'Nachname der anlegenden Person'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('detail_url',        'Link zum Praktikumskalender'),
        ('ablehnungsgrund',   'Begründung der Ablehnung (kann leer sein)'),
    ],
    'practice_grade_confirmed': [
        ('anrede',            'Anredezeile, z. B. „Guten Tag Max Mustermann,"'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum des Praxisabschnitts (TT.MM.JJJJ)'),
        ('bis',               'Enddatum des Praxisabschnitts (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('note',              'Erreichte Note'),
    ],
    'study_day_approved': [
        ('anrede',            'Anredezeile, z. B. „Guten Tag Max Mustermann,"'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('datum',             'Datum des Lerntags (TT.MM.JJJJ)'),
        ('detail_url',        'Link zur Antragsübersicht im Portal'),
    ],
    'study_day_rejected': [
        ('anrede',            'Anredezeile, z. B. „Guten Tag Max Mustermann,"'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('datum',             'Datum des Lerntags (TT.MM.JJJJ)'),
        ('ablehnungsgrund',   'Begründung der Ablehnung (kann leer sein)'),
        ('detail_url',        'Link zur Antragsübersicht im Portal'),
    ],
    'study_day_cancelled': [
        ('anrede',            'Anredezeile, z. B. „Guten Tag Max Mustermann,"'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('datum',             'Datum des stornierten Lerntags (TT.MM.JJJJ)'),
        ('detail_url',        'Link zur Antragsübersicht im Portal'),
    ],
    'assessment_token_sent': [
        ('anrede',            'Vollständige Anredezeile'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('beurteilungs_url',  'Link zum Beurteilungsformular (tokenbasiert)'),
    ],
    'assessment_reminder': [
        ('anrede',            'Vollständige Anredezeile'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('beurteilungs_url',  'Link zum Beurteilungsformular (tokenbasiert)'),
        ('tage_offen',        'Anzahl Tage seit dem ersten Token-Versand'),
    ],
    'assessment_reminder_urgent': [
        ('anrede',            'Vollständige Anredezeile'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('beurteilungs_url',  'Link zum Beurteilungsformular (tokenbasiert)'),
        ('tage_offen',        'Anzahl Tage seit dem ersten Token-Versand'),
        ('eskalation_in_tagen', 'Tage bis zur Eskalation an die Ausbildungskoordination'),
    ],
    'assessment_escalation': [
        ('koordination_name', 'Name der Ausbildungskoordination'),
        ('praxistutor_name',  'Vollständiger Name des Praxistutors'),
        ('praxistutor_email', 'E-Mail-Adresse des Praxistutors'),
        ('student_vorname',   'Vorname der Nachwuchskraft'),
        ('student_nachname',  'Nachname der Nachwuchskraft'),
        ('einheit',           'Name der Organisationseinheit'),
        ('von',               'Startdatum (TT.MM.JJJJ)'),
        ('bis',               'Enddatum (TT.MM.JJJJ)'),
        ('block',             'Name des Ausbildungsblocks'),
        ('tage_offen',        'Anzahl Tage seit dem ersten Token-Versand'),
        ('anzahl_erinnerungen', 'Anzahl bereits gesendeter Erinnerungen'),
        ('detail_url',        'Link zur Beurteilungs-Detailseite (Eingriff durch Koordination)'),
    ],
    'inquiry_new': [
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('betreff',          'Betreff der Anfrage'),
        ('detail_url',       'Link zum Studenten-Detail'),
    ],
    'inquiry_reply': [
        ('anrede',           'Anredezeile'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('betreff',          'Betreff der Anfrage'),
        ('detail_url',       'Link zur Nachricht im Portal'),
    ],
    'document_generated': [
        ('anrede',           'Anredezeile'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('dokument_name',    'Name der Dokumentvorlage'),
    ],
    'change_request_submitted': [
        ('aenderungstyp',    'Lesbarer Name des Änderungstyps (z. B. „Stationswechsel")'),
        ('antragsteller',    'Vor- und Nachname der antragstellenden Person'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Aktuelle Organisationseinheit des Einsatzes'),
        ('zusammenfassung',  'Kurzbeschreibung der gewünschten Änderung'),
        ('begruendung',      'Begründung des Antrags (kann leer sein)'),
        ('detail_url',       'Link zur Antrags-Detailseite (Review)'),
    ],
    'change_request_approved': [
        ('anrede',           'Anredezeile'),
        ('aenderungstyp',    'Lesbarer Name des Änderungstyps'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Organisationseinheit des Einsatzes'),
        ('zusammenfassung',  'Kurzbeschreibung der durchgeführten Änderung'),
        ('detail_url',       'Link zur Nachwuchskraft'),
    ],
    'change_request_rejected': [
        ('anrede',           'Anredezeile'),
        ('aenderungstyp',    'Lesbarer Name des Änderungstyps'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Organisationseinheit des Einsatzes'),
        ('zusammenfassung',  'Kurzbeschreibung des abgelehnten Antrags'),
        ('ablehnungsgrund',  'Begründung der Ablehnung (kann leer sein)'),
        ('detail_url',       'Link zur Nachwuchskraft'),
    ],
    'assignment_decision_for_office': [
        ('entscheidung',     '„angenommen" oder „abgelehnt"'),
        ('student_vorname',  'Vorname der Nachwuchskraft'),
        ('student_nachname', 'Nachname der Nachwuchskraft'),
        ('einheit',          'Organisationseinheit'),
        ('von',              'Startdatum (TT.MM.JJJJ)'),
        ('bis',              'Enddatum (TT.MM.JJJJ)'),
        ('block',            'Name des Ausbildungsblocks'),
        ('ablehnungsgrund',  'Begründung (nur bei Ablehnung)'),
        ('detail_url',       'Link zur Nachwuchskraft'),
    ],
}

NOTIFICATION_DEFAULTS = {
    'instructor_confirmed': {
        'subject': 'Bestellung als Praxistutor: {{ vorname }} {{ nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'Sie wurden als Praxistutor für folgende Organisationseinheit bestellt:\n\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Berufsbilder: {{ berufsbilder }}\n\n'
            'Ihre Bestellung wurde durch die Ausbildungsleitung bestätigt. '
            'Das Bestellungsschreiben finden Sie im Anhang.\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'instructor_confirmed_coordinator': {
        'subject': 'Praxistutor bestätigt: {{ vorname }} {{ nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'der von Ihnen vorgeschlagene Praxistutor wurde durch die Ausbildungsleitung '
            'bestätigt und über die Bestellung informiert:\n\n'
            '  Praxistutor: {{ vorname }} {{ nachname }}\n'
            '  E-Mail: {{ praxistutor_email }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Berufsbilder: {{ berufsbilder }}\n\n'
            'Eine Kopie des Bestellungsschreibens finden Sie im Anhang.\n\n'
            'Zum Praxistutor-Profil:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'instructor_assignment': {
        'subject': 'Neue Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihnen wurde eine Nachwuchskraft für den Praxiseinsatz zugewiesen:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Zeitraum: {{ von }} – {{ bis }}\n'
            '  Block: {{ block }}\n\n'
            'Zum Studentenprofil:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'chief_assignment': {
        'subject': 'Praktikumseinsatz {{ action }}: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'ein Praktikumseinsatz in Ihrem Verantwortungsbereich wurde {{ action }}:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Zeitraum: {{ von }} – {{ bis }}\n'
            '  Block: {{ block }}\n\n'
            'Zu Ihrem Verantwortungsbereich:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'chief_welcome': {
        'subject': 'Willkommen im Azubi-Portal – Bitte Passwort setzen',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'Für Sie wurde ein Konto im Azubi-Portal angelegt.\n'
            'Benutzername: {{ benutzername }}\n\n'
            'Bitte setzen Sie Ihr Passwort über folgenden Link:\n'
            '{{ passwort_url }}\n\n'
            'Der Link ist 3 Tage gültig.\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'reminder_start': {
        'subject': 'Praxiseinsatz beginnt in einer Woche: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'in einer Woche beginnt folgender Praxiseinsatz in Ihrer Betreuung:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Beginn: {{ von }}\n'
            '  Ende: {{ bis }}\n'
            '  Block: {{ block }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'reminder_end': {
        'subject': 'Praxiseinsatz endet in einer Woche: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'in einer Woche endet folgender Praxiseinsatz in Ihrer Betreuung:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Beginn: {{ von }}\n'
            '  Ende: {{ bis }}\n'
            '  Block: {{ block }}\n\n'
            'Bitte denken Sie an die Erstellung einer Praxisbeurteilung für '
            '{{ student_vorname }} {{ student_nachname }}.\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'assignment_approved': {
        'subject': 'Praktikumseinsatz angenommen: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'der folgende Praktikumseinsatz wurde von der Ausbildungskoordination angenommen:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Zeitraum: {{ von }} – {{ bis }}\n'
            '  Block: {{ block }}\n\n'
            'Zur Praktikumsplanung:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'assignment_rejected': {
        'subject': 'Praktikumseinsatz abgelehnt: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'der folgende Praktikumseinsatz wurde von der Ausbildungskoordination abgelehnt:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Zeitraum: {{ von }} – {{ bis }}\n'
            '  Block: {{ block }}\n\n'
            '{% if ablehnungsgrund %}Begründung: {{ ablehnungsgrund }}\n\n'
            '{% endif %}'
            'Bitte nehmen Sie entsprechende Korrekturen vor.\n\n'
            'Zur Praktikumsplanung:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'practice_grade_confirmed': {
        'subject': 'Bewertung Praxisabschnitt: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr Praxisabschnitt wurde bewertet und die Bewertung durch die Ausbildungsleitung bestätigt:\n\n'
            '  Organisationseinheit: {{ einheit }}\n'
            '  Zeitraum: {{ von }} – {{ bis }}\n'
            '  Block: {{ block }}\n'
            '  Note: {{ note }}\n\n'
            'Die Bewertungsdatei finden Sie im Anhang dieser E-Mail.\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'proof_of_training_approved': {
        'subject': 'Ausbildungsnachweis KW {{ kw }}/{{ jahr }} angenommen',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'Ihr Ausbildungsnachweis für die Woche vom {{ von }} bis {{ bis }} (KW {{ kw }}/{{ jahr }}) '
            'wurde angenommen.\n\n'
            'Zum Nachweis:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'student_portal_welcome': {
        'subject': 'Ihr Zugang zum Ausbildungsportal',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'für Sie wurde ein Zugang zum Ausbildungsportal eingerichtet. '
            'Bitte melden Sie sich mit folgenden Zugangsdaten an:\n\n'
            '  Portal: {{ portal_url }}\n'
            '  Benutzername: {{ benutzername }}\n\n'
            'Bitte setzen Sie Ihr Passwort über folgenden Link (gültig für 24 Stunden):\n'
            '{{ passwort_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'proof_of_training_rejected': {
        'subject': 'Ausbildungsnachweis KW {{ kw }}/{{ jahr }}: Korrekturbedarf',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'Ihr Ausbildungsnachweis für die Woche vom {{ von }} bis {{ bis }} (KW {{ kw }}/{{ jahr }}) '
            'wurde mit folgendem Korrekturhinweis zurückgegeben:\n\n'
            '{{ korrekturhinweis }}\n\n'
            'Bitte überarbeiten Sie Ihren Nachweis und reichen Sie ihn erneut ein:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'proof_of_training_reminder': {
        'subject': 'Erinnerung: Ausbildungsnachweis KW {{ kw }}/{{ jahr }}',
        'body': (
            'Guten Tag {{ vorname }} {{ nachname }},\n\n'
            'für die Woche vom {{ von }} bis {{ bis }} (KW {{ kw }}/{{ jahr }}) '
            'liegt noch kein eingereichter Ausbildungsnachweis vor '
            '(Status: {{ status }}).\n\n'
            'Bitte erstellen oder reichen Sie Ihren Nachweis zeitnah ein:\n'
            '{{ portal_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'study_day_approved': {
        'subject': 'Lerntag genehmigt: {{ datum }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr Antrag auf einen Lern- und Studientag am {{ datum }} wurde genehmigt.\n\n'
            'Zur Übersicht Ihrer Lerntage:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'study_day_rejected': {
        'subject': 'Lerntag abgelehnt: {{ datum }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr Antrag auf einen Lern- und Studientag am {{ datum }} wurde leider abgelehnt.\n\n'
            '{% if ablehnungsgrund %}Begründung: {{ ablehnungsgrund }}\n\n{% endif %}'
            'Zur Übersicht Ihrer Lerntage:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'study_day_cancelled': {
        'subject': 'Lerntag storniert: {{ datum }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr genehmigter Lern- und Studientag am {{ datum }} wurde durch das Ausbildungsreferat storniert.\n\n'
            'Zur Übersicht Ihrer Lerntage:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'vacation_approved': {
        'subject': '{{ antragsart }} genehmigt: {{ von }}–{{ bis }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr {{ antragsart }} vom {{ von }} bis {{ bis }} ({{ arbeitstage }} Arbeitstag(e)) '
            'wurde genehmigt und wird der Urlaubsstelle zur Bearbeitung übermittelt.\n\n'
            'Zur Übersicht Ihrer Urlaubsanträge:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'vacation_rejected': {
        'subject': '{{ antragsart }} abgelehnt: {{ von }}–{{ bis }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr {{ antragsart }} vom {{ von }} bis {{ bis }} wurde leider abgelehnt.\n\n'
            '{% if ablehnungsgrund %}Begründung: {{ ablehnungsgrund }}\n\n{% endif %}'
            'Zur Übersicht Ihrer Urlaubsanträge:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'vacation_processed': {
        'subject': '{{ antragsart }} bearbeitet: {{ von }}–{{ bis }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihr {{ antragsart }} vom {{ von }} bis {{ bis }} ({{ arbeitstage }} Arbeitstag(e)) '
            'wurde durch die Urlaubsstelle abschließend bearbeitet.\n\n'
            'Resturlaub aktuelles Jahr: {{ resturlaub_aktuell }} Tag(e)\n'
            'Resturlaub Vorjahr:        {{ resturlaub_vorjahr }} Tag(e)\n\n'
            'Zur Übersicht Ihrer Urlaubsanträge:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'inventory_issued': {
        'subject': 'Ausgabe: {{ gegenstand }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihnen wurde folgender Gegenstand ausgehändigt:\n\n'
            'Gegenstand:     {{ gegenstand }}\n'
            'Seriennummer:   {{ seriennummer }}\n'
            'Kategorie:      {{ kategorie }}\n'
            'Ausgabedatum:   {{ ausgabedatum }}\n'
            'Ausgegeben von: {{ ausgegeben_von }}\n\n'
            'Bitte bewahren Sie dieses Schreiben als Nachweis auf.\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'inventory_returned': {
        'subject': 'Rückgabe bestätigt: {{ gegenstand }}',
        'body': (
            '{{ anrede }}\n\n'
            'Die Rückgabe des folgenden Gegenstands wurde bestätigt:\n\n'
            'Gegenstand:     {{ gegenstand }}\n'
            'Seriennummer:   {{ seriennummer }}\n'
            'Kategorie:      {{ kategorie }}\n'
            'Rückgabedatum:  {{ rueckgabedatum }}\n'
            'Bestätigt von:  {{ bestaetigt_von }}\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'assessment_token_sent': {
        'subject': 'Bitte um Stationsbeurteilung: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'der Praxisabschnitt von {{ student_vorname }} {{ student_nachname }} '
            'in Ihrer Organisationseinheit ({{ einheit }}) endet am {{ bis }}.\n\n'
            'Wir bitten Sie, eine kurze Stationsbeurteilung auszufüllen. '
            'Dies dauert nur wenige Minuten und erfordert keine Anmeldung.\n\n'
            'Zur Beurteilung: {{ beurteilungs_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'assessment_reminder': {
        'subject': 'Erinnerung – Stationsbeurteilung: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'wir möchten Sie freundlich daran erinnern, dass die Stationsbeurteilung für '
            '{{ student_vorname }} {{ student_nachname }} (Einsatz in {{ einheit }} vom {{ von }} '
            'bis {{ bis }}) noch aussteht.\n\n'
            'Der Beurteilungslink ist seit {{ tage_offen }} Tagen aktiv. '
            'Das Ausfüllen dauert nur wenige Minuten und erfordert keine Anmeldung.\n\n'
            'Zur Beurteilung: {{ beurteilungs_url }}\n\n'
            'Vielen Dank für Ihre Unterstützung!\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'assessment_reminder_urgent': {
        'subject': 'DRINGEND: Stationsbeurteilung steht noch aus – {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'trotz mehrfacher Bitte liegt die Stationsbeurteilung für '
            '{{ student_vorname }} {{ student_nachname }} (Einsatz in {{ einheit }} vom {{ von }} '
            'bis {{ bis }}) bisher nicht vor. Der Beurteilungslink ist seit {{ tage_offen }} Tagen aktiv.\n\n'
            'Die Beurteilung ist verbindlicher Bestandteil der Ausbildungsdokumentation. '
            'Bitte holen Sie das Ausfüllen kurzfristig nach.\n\n'
            'Sollte bis in {{ eskalation_in_tagen }} Tagen keine Beurteilung vorliegen, müssen wir '
            'die zuständige Ausbildungskoordination informieren, damit der Vorgang weiter bearbeitet '
            'werden kann.\n\n'
            'Zur Beurteilung: {{ beurteilungs_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Ausbildungsreferat'
        ),
    },
    'assessment_escalation': {
        'subject': 'Eskalation: Ausstehende Stationsbeurteilung – {{ student_vorname }} {{ student_nachname }}',
        'body': (
            'Guten Tag,\n\n'
            'die Stationsbeurteilung für {{ student_vorname }} {{ student_nachname }} '
            '(Einsatz in {{ einheit }} im Block „{{ block }}", {{ von }} – {{ bis }}) ist trotz '
            '{{ anzahl_erinnerungen }} Erinnerung(en) seit {{ tage_offen }} Tagen ausstehend.\n\n'
            'Praxistutor: {{ praxistutor_name }} <{{ praxistutor_email }}>\n\n'
            'Bitte prüfen Sie den Vorgang. Sie können in der Detailansicht den Token verlängern, '
            'einen anderen Praxistutoren eintragen oder den Vorgang abschließen:\n'
            '{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'inquiry_new': {
        'subject': 'Neue Anfrage: {{ betreff }}',
        'body': (
            'Guten Tag,\n\n'
            '{{ student_vorname }} {{ student_nachname }} hat eine neue Anfrage gestellt:\n\n'
            '  Betreff: {{ betreff }}\n\n'
            'Zur Nachwuchskraft:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'inquiry_reply': {
        'subject': 'Antwort zu Ihrer Anfrage: {{ betreff }}',
        'body': (
            '{{ anrede }}\n\n'
            'zu Ihrer Anfrage „{{ betreff }}" liegt eine neue Antwort vom Ausbildungsreferat vor.\n\n'
            'Zur Nachricht:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'document_generated': {
        'subject': 'Ihre Bescheinigung: {{ dokument_name }}',
        'body': (
            '{{ anrede }}\n\n'
            'Ihre Bescheinigung „{{ dokument_name }}" wurde erstellt. '
            'Sie finden das Dokument als PDF im Anhang dieser E-Mail.\n\n'
            'Das Dokument wurde außerdem in Ihrer Akte abgelegt.\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'change_request_submitted': {
        'subject': 'Neuer Änderungsantrag: {{ aenderungstyp }} – {{ student_vorname }} {{ student_nachname }}',
        'body': (
            'Guten Tag,\n\n'
            'die Ausbildungskoordination hat einen Änderungsantrag für einen '
            'Praktikumseinsatz gestellt:\n\n'
            '  Antragsteller:    {{ antragsteller }}\n'
            '  Änderungstyp:     {{ aenderungstyp }}\n'
            '  Nachwuchskraft:   {{ student_vorname }} {{ student_nachname }}\n'
            '  Einheit:          {{ einheit }}\n'
            '  Beantragt:        {{ zusammenfassung }}\n\n'
            '{% if begruendung %}Begründung: {{ begruendung }}\n\n{% endif %}'
            'Zur Bearbeitung:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'change_request_approved': {
        'subject': 'Änderungsantrag genehmigt: {{ aenderungstyp }} – {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'der folgende Änderungsantrag wurde von der Ausbildungsleitung genehmigt '
            'und ist bereits umgesetzt:\n\n'
            '  Änderungstyp:   {{ aenderungstyp }}\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Einheit:        {{ einheit }}\n'
            '  Änderung:       {{ zusammenfassung }}\n\n'
            'Zur Nachwuchskraft:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'change_request_rejected': {
        'subject': 'Änderungsantrag abgelehnt: {{ aenderungstyp }} – {{ student_vorname }} {{ student_nachname }}',
        'body': (
            '{{ anrede }}\n\n'
            'der folgende Änderungsantrag wurde von der Ausbildungsleitung abgelehnt:\n\n'
            '  Änderungstyp:   {{ aenderungstyp }}\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Einheit:        {{ einheit }}\n'
            '  Beantragt war:  {{ zusammenfassung }}\n\n'
            '{% if ablehnungsgrund %}Begründung: {{ ablehnungsgrund }}\n\n{% endif %}'
            'Zur Nachwuchskraft:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
    'assignment_decision_for_office': {
        'subject': 'Praktikumseinsatz {{ entscheidung }}: {{ student_vorname }} {{ student_nachname }}',
        'body': (
            'Guten Tag,\n\n'
            'der folgende Praktikumseinsatz wurde von der Ausbildungskoordination '
            '{{ entscheidung }}:\n\n'
            '  Nachwuchskraft: {{ student_vorname }} {{ student_nachname }}\n'
            '  Einheit:        {{ einheit }}\n'
            '  Zeitraum:       {{ von }} – {{ bis }}\n'
            '  Block:          {{ block }}\n\n'
            '{% if ablehnungsgrund %}Begründung der Ablehnung: {{ ablehnungsgrund }}\n\n{% endif %}'
            'Zur Nachwuchskraft:\n{{ detail_url }}\n\n'
            'Mit freundlichen Grüßen\nIhr Azubi-Portal'
        ),
    },
}


class NotificationTemplate(models.Model):
    """Konfigurierbare E-Mail-Vorlage für systemweite Benachrichtigungen."""

    key = models.CharField(
        max_length=50,
        unique=True,
        choices=NOTIFICATION_KEYS,
        verbose_name='Typ',
    )
    subject = models.CharField(max_length=250, verbose_name='Betreff')
    body = models.TextField(verbose_name='Text')

    class Meta:
        verbose_name = 'Benachrichtigungsvorlage'
        verbose_name_plural = 'Benachrichtigungsvorlagen'
        ordering = ['key']

    def __str__(self):
        return self.get_key_display()

    @classmethod
    def render(cls, key: str, context: dict) -> tuple[str, str]:
        """
        Gibt (subject, body) zurück, gerendert mit den übergebenen Variablen.
        Existiert noch keine Vorlage für den Key, wird sie mit dem Default angelegt.
        """
        from django.template import Template, Context

        defaults = NOTIFICATION_DEFAULTS.get(key, {'subject': key, 'body': ''})
        obj, _ = cls.objects.get_or_create(key=key, defaults=defaults)

        ctx = Context(context, autoescape=False)
        subject = Template(obj.subject).render(ctx)
        body = Template(obj.body).render(ctx)
        return subject, body


HOLIDAY_STATE_CHOICES = [
    ('',   'Keine (nur bundesweite Feiertage)'),
    ('BB', 'Brandenburg'),
    ('BE', 'Berlin'),
    ('BW', 'Baden-Württemberg'),
    ('BY', 'Bayern'),
    ('HB', 'Bremen'),
    ('HE', 'Hessen'),
    ('HH', 'Hamburg'),
    ('MV', 'Mecklenburg-Vorpommern'),
    ('NI', 'Niedersachsen'),
    ('NW', 'Nordrhein-Westfalen'),
    ('RP', 'Rheinland-Pfalz'),
    ('SH', 'Schleswig-Holstein'),
    ('SL', 'Saarland'),
    ('SN', 'Sachsen'),
    ('ST', 'Sachsen-Anhalt'),
    ('TH', 'Thüringen'),
]


class Adress(models.Model):
    """Postanschrift (Straße, Hausnummer, PLZ, Ort, Bundesland)."""

    street = models.CharField(max_length=200, verbose_name="Straße")
    house_number = models.CharField(max_length=20, verbose_name="Hausnummer")
    zip_code = models.CharField(max_length=10, verbose_name="PLZ")
    city = models.CharField(max_length=100, verbose_name="Ort")
    holiday_state = models.CharField(
        max_length=2,
        blank=True,
        choices=HOLIDAY_STATE_CHOICES,
        default='',
        verbose_name="Bundesland (Feiertage)",
        help_text="Bundesland der Adresse; wird für die Feiertagsberechnung von "
                  "Anwesenden an diesem Standort verwendet.",
    )

    def __str__(self) -> str:
        return f"{self.street} {self.house_number}, {self.zip_code} {self.city}"

    class Meta:
        verbose_name = "Adresse"
        verbose_name_plural = "Adressen"


class Gender(models.Model):
    """Geschlecht mit Abkürzung und Anredeform."""

    abbreviation = models.CharField(
        primary_key=True,
        unique=True,
        max_length=1,
        verbose_name="Abkürzung"
    )
    gender = models.CharField(
        max_length=100,
        default="",
        verbose_name="Geschlecht"
    )
    description = models.CharField(
        max_length=100,
        default="",
        verbose_name="Beschreibung/Anrede"
    )

    def __str__(self):
        return f"{self.description}"

    class Meta:
        db_table = 'student_gender'
        verbose_name = "Geschlecht"
        verbose_name_plural = "Geschlechter"


class UserProfile(models.Model):
    """Erweitertes Profil für Django-Nutzer."""
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Benutzer",
    )
    job_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Funktion",
    )
    location = models.ForeignKey(
        'organisation.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Standort",
    )
    room = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Raum",
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Durchwahl",
    )

    def __str__(self):
        return f"Profil von {self.user.get_full_name() or self.user.username}"

    class Meta:
        verbose_name = "Benutzerprofil"
        verbose_name_plural = "Benutzerprofile"
        permissions = [
            (
                'reset_user_2fa',
                'Darf 2FA-Verknüpfungen anderer Benutzer zurücksetzen',
            ),
        ]


class AusbildungsreferatProfile(models.Model):
    """Individuelle Zuständigkeiten und Berechtigungen für Mitarbeitende im Ausbildungsreferat."""
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='ausbildungsreferat_profile',
        verbose_name="Benutzer",
    )
    job_profiles = models.ManyToManyField(
        'course.JobProfile',
        blank=True,
        verbose_name="Zuständige Berufsbilder",
    )
    can_manage_dormitory = models.BooleanField(default=False, verbose_name="Wohnheimverwaltung")
    can_manage_inventory = models.BooleanField(default=False, verbose_name="Inventarverwaltung")
    can_manage_absences = models.BooleanField(default=False, verbose_name="Abwesenheitsverwaltung")
    can_approve_vacation = models.BooleanField(default=False, verbose_name="Urlaubsgenehmigung")
    can_approve_study_days = models.BooleanField(default=False, verbose_name="Lerntage-Genehmigung")
    can_manage_announcements = models.BooleanField(default=False, verbose_name="Ankündigungen verwalten")
    can_manage_interventions = models.BooleanField(default=False, verbose_name="Maßnahmen verwalten")

    def __str__(self):
        return f"Referat-Profil von {self.user.get_full_name() or self.user.username}"

    class Meta:
        verbose_name = "Ausbildungsreferat-Profil"
        verbose_name_plural = "Ausbildungsreferat-Profile"


class SiteConfiguration(models.Model):
    """Singleton-Modell für siteweite Konfiguration."""

    # ── Seiteninhalte ─────────────────────────────────────────────────────────
    impressum_text = models.TextField(blank=True, verbose_name="Impressum-Text")
    datenschutz_text = models.TextField(blank=True, verbose_name="Datenschutz-Text")

    # ── Erscheinungsbild ──────────────────────────────────────────────────────
    brand_name = models.CharField(
        max_length=50, default='azubi.', verbose_name="App-Name",
        help_text="Wird in der Navigationsleiste und im Browser-Tab angezeigt.")
    brand_header = models.CharField(default='Eine offizielle Anwendung der Abteilung X in der Bundesbehörde Z', max_length=175, verbose_name="Kopfzeile",help_text="Wird in der Kopfzeile über der Navigationsleiste angezeigt.")
    brand_primary_color     = models.CharField(max_length=7, default='#0d6efd', verbose_name="Primärfarbe")
    brand_secondary_color   = models.CharField(max_length=7, default='#6c757d', verbose_name="Sekundärfarbe")
    brand_success_color     = models.CharField(max_length=7, default='#198754', verbose_name="Erfolg")
    brand_danger_color      = models.CharField(max_length=7, default='#dc3545', verbose_name="Gefahr")
    brand_warning_color     = models.CharField(max_length=7, default='#ffc107', verbose_name="Warnung")
    brand_info_color        = models.CharField(max_length=7, default='#0dcaf0', verbose_name="Info")

    # ── Hintergrundaufgaben ───────────────────────────────────────────────────

    # Erinnerungen Praxiseinsätze
    reminder_days_before_start = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="Vorlauf Einsatzbeginn (Tage)",
        help_text="Wie viele Tage vor Beginn eines Praxiseinsatzes der Praxistutor erinnert wird.",
    )
    reminder_days_before_end = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="Vorlauf Einsatzende (Tage)",
        help_text="Wie viele Tage vor Ende eines Praxiseinsatzes der Praxistutor erinnert wird.",
    )
    reminder_hour = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="Uhrzeit Erinnerungen (Stunde)",
        help_text="Stunde (0–23), zu der die Praxiseinsatz-Erinnerungen und Ausbildungsnachweis-Erinnerungen versendet werden.",
    )
    reminder_minute = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Uhrzeit Erinnerungen (Minute)",
        help_text="Minute (0–59).",
    )

    # Eskalation Praxistutoren-Beurteilungen (3-stufig)
    escalation_stage1_days = models.PositiveSmallIntegerField(
        default=3,
        verbose_name="Eskalation Stufe 1: Erste Erinnerung (Tage)",
        help_text="Tage nach Token-Versand, bis die erste Erinnerung an den Praxistutor geht.",
    )
    escalation_stage2_days = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="Eskalation Stufe 2: Zweite Erinnerung (Tage)",
        help_text="Tage nach erster Erinnerung, bis die zweite (schärfere) Erinnerung gesendet wird.",
    )
    escalation_final_days = models.PositiveSmallIntegerField(
        default=14,
        verbose_name="Eskalation Stufe 3: Information an Koordination (Tage)",
        help_text="Tage nach Token-Versand, bis die zuständige Ausbildungskoordination informiert wird.",
    )

    # Anonymisierung
    anonymization_months = models.PositiveSmallIntegerField(
        default=12,
        verbose_name="Anonymisierungsfrist (Monate)",
        help_text="Nach wie vielen Monaten Inaktivität (Statuswechsel) eine Nachwuchskraft anonymisiert wird.",
    )
    anonymization_hour = models.PositiveSmallIntegerField(
        default=12,
        verbose_name="Uhrzeit Anonymisierung (Stunde)",
        help_text="Stunde (0–23), zu der die nächtliche Anonymisierung läuft.",
    )
    anonymization_minute = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Uhrzeit Anonymisierung (Minute)",
        help_text="Minute (0–59).",
    )

    # Urlaubsanträge an Urlaubsstelle
    vacation_batch_hour = models.PositiveSmallIntegerField(
        default=8,
        verbose_name="Uhrzeit Urlaubsantragspaket (Stunde)",
        help_text="Stunde (0–23), zu der genehmigte Urlaubsanträge gebündelt an die Urlaubsstelle gesendet werden.",
    )
    vacation_batch_minute = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Uhrzeit Urlaubsantragspaket (Minute)",
        help_text="Minute (0–59).",
    )

    # Krank-/Gesundmeldungen an Urlaubsstelle
    sick_leave_report_hour = models.PositiveSmallIntegerField(
        default=8,
        verbose_name="Uhrzeit Krankmeldungsbericht (Stunde)",
        help_text="Stunde (0–23), zu der der tägliche Bericht über Krank- und Gesundmeldungen versendet wird.",
    )
    sick_leave_report_minute = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="Uhrzeit Krankmeldungsbericht (Minute)",
        help_text="Minute (0–59).",
    )

    # Eskalation Stationsbeurteilungen
    assessment_escalation_hour = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="Uhrzeit Eskalationslauf (Stunde)",
        help_text="Stunde (0–23), zu der täglich der Eskalationslauf für ausstehende Stationsbeurteilungen läuft.",
    )
    assessment_escalation_minute = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Uhrzeit Eskalationslauf (Minute)",
        help_text="Minute (0–59).",
    )

    # Paperless-Eingangskorb-Cache
    paperless_cache_interval_seconds = models.PositiveIntegerField(
        default=120,
        verbose_name="Paperless-Cache-Intervall (Sekunden)",
        help_text="Wie oft (in Sekunden) der Paperless-Eingangskorb-Cache aktualisiert wird.",
    )

    # Tägliche Backups (DB + Media + Paperless)
    backup_hour = models.PositiveSmallIntegerField(
        default=2,
        verbose_name="Uhrzeit Backup (Stunde)",
        help_text="Stunde (0–23), zu der das tägliche Backup von Datenbank, Media und Paperless läuft.",
    )
    backup_minute = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Uhrzeit Backup (Minute)",
        help_text="Minute (0–59).",
    )
    backup_offsite_hour = models.PositiveSmallIntegerField(
        default=3,
        verbose_name="Uhrzeit Off-Site-Sync (Stunde)",
        help_text="Stunde, zu der lokale Backups via restic auf das NAS gespiegelt werden.",
    )
    backup_offsite_minute = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Uhrzeit Off-Site-Sync (Minute)",
        help_text="Minute (0–59).",
    )
    backup_keep_weekly = models.PositiveSmallIntegerField(
        default=4,
        verbose_name="Wöchentliche Backups vorhalten",
        help_text="Anzahl wöchentlicher Backups, die zusätzlich zu den täglichen vorgehalten werden.",
    )
    backup_keep_monthly = models.PositiveSmallIntegerField(
        default=12,
        verbose_name="Monatliche Backups vorhalten",
        help_text="Anzahl monatlicher Backups (Jahres-Historie).",
    )

    # ── Integrationen ────────────────────────────────────────────────────────
    paperless_url = models.URLField(
        max_length=200, blank=True, default='',
        verbose_name="Paperless-ngx URL",
        help_text="Basis-URL der Paperless-ngx-Instanz, z.\u202fB. http://paperless:8000",
    )
    paperless_api_key = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Paperless-ngx API-Key",
        help_text="API-Token eines Paperless-Nutzers mit ausreichenden Berechtigungen.",
    )

    # ── Module ────────────────────────────────────────────────────────────────
    module_dormitory       = models.BooleanField(default=True, verbose_name="Wohnheimverwaltung")
    module_inventory       = models.BooleanField(default=True, verbose_name="Inventar")
    module_absence         = models.BooleanField(default=True, verbose_name="Abwesenheiten")
    module_studyday        = models.BooleanField(default=True, verbose_name="Lerntage")
    module_assessment      = models.BooleanField(default=True, verbose_name="Beurteilungen")
    module_intervention    = models.BooleanField(default=True, verbose_name="Maßnahmen")
    module_announcements   = models.BooleanField(default=True, verbose_name="Ankündigungen")
    module_knowledge       = models.BooleanField(default=True, verbose_name="Wissensdatenbank")
    module_proofoftraining = models.BooleanField(default=True, verbose_name="Ausbildungsnachweise")
    module_auditlog        = models.BooleanField(default=True, verbose_name="Audit-Log")

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name = "Website-Konfiguration"
        verbose_name_plural = "Website-Konfiguration"


# ── Interne Benachrichtigungen ─────────────────────────────────────────────────

class Notification(models.Model):
    """Interne Benachrichtigung für einen Benutzer."""
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='internal_notifications',
        verbose_name='Empfänger',
    )
    message = models.CharField(max_length=300, verbose_name='Nachricht')
    link = models.CharField(max_length=500, blank=True, verbose_name='Link')
    icon = models.CharField(max_length=60, default='bi-bell', verbose_name='Icon')
    category = models.CharField(max_length=100, blank=True, verbose_name='Kategorie')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Gelesen am')

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return f'{self.user.username}: {self.message[:60]}'

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Interne Benachrichtigung'
        verbose_name_plural = 'Interne Benachrichtigungen'


# ── E-Mail-Präferenzen ────────────────────────────────────────────────────────

# Benachrichtigungsschlüssel, die Benutzer abwählen können (mit lesbaren Labels).
# Nicht aufgeführte Schlüssel werden immer gesendet (z. B. Willkommens-Mails).
CONFIGURABLE_NOTIFICATION_KEYS = [
    # Nachwuchskräfte
    ('proof_of_training_reminder', 'Erinnerung bei fehlendem Ausbildungsnachweis'),
    ('proof_of_training_approved', 'Bestätigung: Ausbildungsnachweis angenommen'),
    ('proof_of_training_rejected', 'Rückmeldung: Ausbildungsnachweis Korrekturbedarf'),
    # Ausbildungskoordination
    ('chief_assignment', 'Benachrichtigung: Praxiseinsatz angelegt / geändert'),
    ('change_request_approved', 'Änderungsantrag: Antrag genehmigt'),
    ('change_request_rejected', 'Änderungsantrag: Antrag abgelehnt'),
    # Ausbildungsreferat / Ausbildungsleitung
    ('assignment_approved', 'Rückmeldung: Einsatz angenommen'),
    ('assignment_rejected', 'Rückmeldung: Einsatz abgelehnt'),
    ('change_request_submitted', 'Änderungsantrag: Neuer Antrag eingegangen'),
    ('assignment_decision_for_office', 'Praktikumseinsatz: Entscheidung der Koordination'),
]


class UserNotificationPreference(models.Model):
    """Speichert, welche E-Mail-Benachrichtigungen ein Benutzer deaktiviert hat."""

    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='notification_prefs',
        verbose_name='Benutzer',
    )
    disabled_keys = models.JSONField(
        default=list,
        verbose_name='Deaktivierte Benachrichtigungen',
        help_text='Liste der deaktivierten Notification-Keys',
    )

    class Meta:
        verbose_name = 'E-Mail-Präferenz'
        verbose_name_plural = 'E-Mail-Präferenzen'

    def __str__(self):
        return f'Präferenzen von {self.user.get_full_name() or self.user.username}'


# ── Dashboard-Konfiguration ──────────────────────────────────────────────────

# Widget-Definitionen je Dashboard-Typ
DASHBOARD_WIDGETS = {
    'leitung': [
        {'id': 'birthdays',          'label': 'Geburtstage',             'icon': 'bi-balloon-heart',       'default': True},
        {'id': 'upcoming_blocks',    'label': 'Anstehende Blöcke',      'icon': 'bi-calendar3',           'default': True},
        {'id': 'pending_letters',    'label': 'Ausstehende Schreiben',  'icon': 'bi-envelope-open',       'default': True},
        {'id': 'fehlzeiten',         'label': 'Fehlzeiten-Ampel',       'icon': 'bi-activity',            'default': True},
        {'id': 'course_progress',    'label': 'Kursfortschritt',        'icon': 'bi-journals',            'default': True},
        {'id': 'ending_soon',        'label': 'Ablaufende Einsätze',    'icon': 'bi-hourglass-split',     'default': True},
        {'id': 'dormitory',          'label': 'Wohnheim-Belegung',      'icon': 'bi-building',            'default': True},
        {'id': 'station_utilization','label': 'Stationsauslastung',     'icon': 'bi-speedometer2',        'default': True},
        {'id': 'pending_internships','label': 'Ausstehende Einsätze',   'icon': 'bi-briefcase',           'default': True},
        {'id': 'open_interventions', 'label': 'Offene Maßnahmen',       'icon': 'bi-exclamation-triangle','default': True},
        {'id': 'open_inquiries',     'label': 'Offene Anfragen',        'icon': 'bi-chat-left-text',      'default': True},
        {'id': 'recently_rejected',  'label': 'Abgelehnte Nachweise',   'icon': 'bi-journal-x',           'default': True},
    ],
    'koord': [
        {'id': 'birthdays',          'label': 'Geburtstage',             'icon': 'bi-balloon-heart',       'default': True},
        {'id': 'koord_training',     'label': 'Eingereichte Nachweise', 'icon': 'bi-journal-check',       'default': True},
        {'id': 'koord_pending',      'label': 'Ausstehende Einsätze',   'icon': 'bi-briefcase',           'default': True},
        {'id': 'koord_ending_soon',  'label': 'Ablaufende Einsätze',    'icon': 'bi-hourglass-split',     'default': True},
    ],
}


class DashboardConfig(models.Model):
    """Benutzerspezifische Dashboard-Konfiguration (Widget-Sichtbarkeit & Reihenfolge)."""
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='dashboard_config',
        verbose_name='Benutzer',
    )
    widget_order = models.JSONField(
        default=list,
        verbose_name='Widget-Reihenfolge',
        help_text='Liste von Widget-IDs in gewünschter Reihenfolge.',
    )
    hidden_widgets = models.JSONField(
        default=list,
        verbose_name='Ausgeblendete Widgets',
        help_text='Liste von Widget-IDs, die ausgeblendet sind.',
    )

    class Meta:
        verbose_name = 'Dashboard-Konfiguration'
        verbose_name_plural = 'Dashboard-Konfigurationen'

    def __str__(self):
        return f'Dashboard von {self.user.get_full_name() or self.user.username}'

    def get_ordered_widgets(self, dashboard_type):
        """Gibt die Widgets in benutzerdefinierter Reihenfolge zurück, mit Sichtbarkeits-Flag."""
        definitions = DASHBOARD_WIDGETS.get(dashboard_type, [])
        hidden = set(self.hidden_widgets or [])
        order = self.widget_order or []

        # Widgets nach benutzerdefinierter Reihenfolge sortieren
        ordered = []
        seen = set()
        for wid in order:
            defn = next((d for d in definitions if d['id'] == wid), None)
            if defn:
                ordered.append({**defn, 'visible': wid not in hidden})
                seen.add(wid)
        # Restliche (neue) Widgets ans Ende
        for defn in definitions:
            if defn['id'] not in seen:
                ordered.append({**defn, 'visible': defn['id'] not in hidden})
        return ordered


def create_notification(user, message, link='', icon='bi-bell', category=''):
    """Erstellt eine interne Benachrichtigung für einen Benutzer."""
    Notification.objects.create(
        user=user,
        message=message[:300],
        link=link,
        icon=icon,
        category=category,
    )


def notify_staff(message, link='', icon='bi-bell', category=''):
    """Benachrichtigt alle Ausbildungsleitung- und Ausbildungsreferat-Benutzer."""
    from django.contrib.auth.models import Group, User
    recipients = User.objects.filter(
        groups__name__in=['ausbildungsleitung', 'ausbildungsreferat'],
        is_active=True,
    ).distinct()
    for user in recipients:
        create_notification(user, message, link=link, icon=icon, category=category)


# ── Reporting: gespeicherte Sichten ──────────────────────────────────────────

class SavedReportView(models.Model):
    """Vom Power-User gespeicherte Filter-/Spalten-Konfiguration zu einem Report.

    Reports selbst sind im Code definiert (``services.reports``).
    Eine SavedReportView speichert lediglich die Frontend-Konfiguration
    (welche Spalten, welche Filter-Werte) als JSON.
    """
    report_slug = models.CharField(
        max_length=100,
        verbose_name='Report-Slug',
        help_text='Verweist auf einen Code-Report aus services.reports.',
    )
    name = models.CharField(max_length=120, verbose_name='Name der Sicht')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    owner = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='saved_report_views',
        verbose_name='Eigentümer',
    )
    filters_json = models.JSONField(
        default=dict, blank=True,
        verbose_name='Filter-Konfiguration',
        help_text='Filter-Werte als JSON (Schlüssel = Filter-Key).',
    )
    columns_json = models.JSONField(
        default=list, blank=True,
        verbose_name='Spalten-Auswahl',
        help_text='Liste der sichtbaren Column-Keys in gewünschter Reihenfolge. Leer = alle.',
    )
    shared = models.BooleanField(
        default=False,
        verbose_name='Mit anderen Power-Usern teilen',
        help_text='Wenn aktiv, sehen Ausbildungsleitung und -referat diese Sicht ebenfalls.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Gespeicherte Auswertungs-Sicht'
        verbose_name_plural = 'Gespeicherte Auswertungs-Sichten'
        ordering = ['report_slug', 'name']

    def __str__(self):
        return f'{self.name} ({self.report_slug})'


class CustomReport(models.Model):
    """Frontend-konfigurierter Report (Query-Builder).

    Die ``definition`` ist ein JSON, das vom Builder gefüllt wird:

    .. code-block:: json

        {
          "datasource": "assignments",
          "select":     ["student__first_name", "unit__name"],
          "filters":    [{"field": "status", "op": "exact", "value": "approved"}],
          "group_by":   [],
          "aggregations": [],
          "order_by":   ["-end_date"],
          "limit":      1000
        }
    """
    name = models.CharField(max_length=120, verbose_name='Name')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    category = models.CharField(
        max_length=60,
        default='Eigene Reports',
        verbose_name='Kategorie',
    )
    owner = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='custom_reports',
        verbose_name='Eigentümer',
    )
    definition = models.JSONField(
        default=dict,
        verbose_name='Definition',
        help_text='JSON: datasource, select, filters, group_by, aggregations, order_by, limit.',
    )
    shared = models.BooleanField(
        default=False,
        verbose_name='Mit anderen Power-Usern teilen',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Eigener Report'
        verbose_name_plural = 'Eigene Reports'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name

    @property
    def slug(self):
        return f'custom-{self.pk}'
