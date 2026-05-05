# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Einheitliche Platzhalter-Konvention für alle generierten Word-Dokumente.

Diese Datei ist die zentrale Quelle der Wahrheit. Sowohl die Context-Helper
in :mod:`document.contexts` als auch die Hilfetexte in der Vorlagen-
Verwaltung speisen sich daraus, damit Code und Dokumentation nicht
auseinanderlaufen.

Konvention (in allen Vorlagen einheitlich):
    {{ präfix_feld }}    – snake_case, deutsch, Präfix nach Domäne.
    {{ heute }}          – ohne Präfix (globaler Meta-Wert).
    {{ freitext }}       – Freitext-Eingabe (wo zutreffend, view-spezifisch).
    {{ zeichnung }}      – Schlusszeichen am Ende des Dokuments.

Listen werden im Plural verwendet (z.B. ``einsaetze``, ``berufsbilder``,
``nachweise``, ``antraege``). Innerhalb einer Liste gelten die gleichen
Felder wie in der entsprechenden Einzelobjekt-Konvention.
"""

# ── Nachwuchskraft ──────────────────────────────────────────────────────────
STUDENT_TAGS = {
    'student_vorname':           'Vorname',
    'student_nachname':          'Nachname',
    'student_anrede':            'Anrede (Frau / Herr / leer)',
    'student_id':                'Interne Nachwuchskraft-ID',
    'student_geburtsdatum':      'Geburtsdatum (TT.MM.JJJJ)',
    'student_geburtsort':        'Geburtsort',
    'student_email_privat':      'Private E-Mail',
    'student_email_dienstlich':  'Dienstliche E-Mail-Kennung',
    'student_telefon':           'Telefonnummer',
    'student_adresse':           'Postanschrift (Straße/Nr.\\nPLZ Ort)',
}

# ── Kurs / Berufsbild ───────────────────────────────────────────────────────
COURSE_TAGS = {
    'kurs_titel':                          'Kurs-Titel',
    'kurs_beginn':                         'Kursbeginn (TT.MM.JJJJ)',
    'kurs_ende':                           'Kursende (TT.MM.JJJJ)',
    'kurs_berufsbild':                     'Berufsbild',
    'kurs_berufsbild_beschreibung':        'Beschreibung des Berufsbilds',
    'kurs_berufsbild_abschluss':           'Abschluss',
    'kurs_berufsbild_gesetzesgrundlage':   'Gesetzesgrundlage',
    'kurs_berufsbild_laufbahn':            'Laufbahn',
    'kurs_berufsbild_fachrichtung':        'Fachrichtung',
}

# ── Block ───────────────────────────────────────────────────────────────────
BLOCK_TAGS = {
    'block_name':              'Bezeichnung des Blocks',
    'block_beginn':            'Blockbeginn',
    'block_ende':               'Blockende',
    'block_standort':          'Standort des Blocks',
    'block_standort_adresse':  'Adresse des Block-Standorts',
}

# ── Einsatz (einzeln oder als Liste „einsaetze") ────────────────────────────
EINSATZ_TAGS = {
    'einsatz_einheit':              'Organisationseinheit',
    'einsatz_einheit_beschreibung': 'Beschreibung der Einheit',
    'einsatz_beginn':               'Einsatzbeginn',
    'einsatz_ende':                 'Einsatzende',
    'einsatz_standort':             'Standort',
    'einsatz_praxistutor':          'Name des Praxistutors',
}

# ── Praxistutor (Empfänger eines Bestellschreibens) ─────────────────────────
INSTRUCTOR_TAGS = {
    'praxistutor':           'Vollständiger Name',
    'praxistutor_vorname':   'Vorname',
    'praxistutor_nachname':  'Nachname',
    'praxistutor_email':     'E-Mail',
    'praxistutor_einheit':   'Organisationseinheit',
    'praxistutor_standort':  'Standort',
}

# ── Wohnheim / Reservierung ─────────────────────────────────────────────────
DORMITORY_TAGS = {
    'wohnheim_name':       'Name des Wohnheims',
    'wohnheim_adresse':    'Anschrift',
    'zimmer_nummer':       'Zimmernummer',
    'belegung_beginn':     'Belegungsbeginn',
    'belegung_ende':       'Belegungsende',
}

# ── Inventar / Ausgabe ──────────────────────────────────────────────────────
INVENTORY_TAGS = {
    'gegenstand_bezeichnung':   'Bezeichnung des Gegenstands',
    'gegenstand_seriennummer':  'Seriennummer',
    'gegenstand_kategorie':     'Kategorie',
    'ausgabe_datum':            'Ausgabedatum (Alias auf {{ heute }})',
    'qr_code':                  'QR-Code als Bild (InlineImage)',
}

# ── Ersteller (in JEDEM Dokument verfügbar) ─────────────────────────────────
CREATOR_TAGS = {
    'ersteller_name':       'Vollständiger Name',
    'ersteller_vorname':    'Vorname',
    'ersteller_nachname':   'Nachname',
    'ersteller_funktion':   'Funktion / Job-Title',
    'ersteller_standort':   'Standort des Erstellers',
    'ersteller_raum':       'Raum',
    'ersteller_durchwahl':  'Durchwahl',
    'zeichnung':            'Schlusszeichen (in der Regel der Nachname)',
}

# ── Meta (in JEDEM Dokument verfügbar) ──────────────────────────────────────
META_TAGS = {
    'heute':     'Heutiges Datum (TT.MM.JJJJ)',
    'freitext':  'Freitext aus dem Generierungsformular (sofern vorgesehen)',
}


def format_help_block(*tag_dicts: dict, list_hints: list[str] | None = None) -> str:
    """Erzeugt einen Hilfetext-Block (Plain Text) aus mehreren Tag-Dicts.

    Wird in den Hilfetexten unter den Vorlagen-Tabs verwendet, damit die
    Doku nicht aus Code-Kommentaren rausgewachsen ist.
    """
    parts = []
    for d in tag_dicts:
        parts.append(", ".join("{{ " + key + " }}" for key in d.keys()))
    if list_hints:
        parts.append(" | ".join(list_hints))
    return " | ".join(parts)