# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""iCal-/ICS-Helper für Outlook-/Exchange-kompatible Termin-Mails.

Erzeugt RFC-5545-konforme VEVENTs (über die `icalendar`-Library) und liefert
fertige `attachments`-Tupel im von ``services.email.send_mail`` erwarteten
Format ``(filename, bytes, mimetype)``.

Drei öffentliche Helfer:

* :func:`build_event_ics`         – baut ein einzelnes VEVENT als ICS-bytes
* :func:`ics_attachment_tuple`    – wickelt es in das Attachment-Tupel
* :func:`stable_uid`              – deterministische, lebenszeit-stabile UID
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from icalendar import Calendar, Event, vCalAddress, vText

BERLIN = ZoneInfo('Europe/Berlin')

ICS_PRODID = '-//Azubi-App//Ausbildungsmanagement//DE'

# Erlaubte iCal-Methoden – siehe RFC 5546.
METHOD_REQUEST = 'REQUEST'
METHOD_CANCEL  = 'CANCEL'
METHOD_PUBLISH = 'PUBLISH'


def stable_uid(instance, kind: str) -> str:
    """Erzeugt eine über die Lebenszeit stabile UID für ein VEVENT.

    Outlook erkennt Updates anhand identischer ``UID`` + steigender ``SEQUENCE``.
    Solange der Primary-Key der Instanz nicht geändert wird (was nie passieren
    sollte), bleibt die UID stabil – Updates werden korrekt zugeordnet.

    Beispiel: ``einsatz-ASSIGN-0042@azubi.behoerde.de``
    """
    domain = getattr(settings, 'CALENDAR_UID_DOMAIN', 'azubi.local')
    return f'{kind}-{instance.pk}@{domain}'


def build_event_ics(
    *,
    uid: str,
    summary: str,
    start: date | datetime,
    end: date | datetime,
    description: str = '',
    location: str = '',
    organizer_email: str | None = None,
    attendee_emails: list[str] | None = None,
    sequence: int = 0,
    method: str = METHOD_REQUEST,
    url: str | None = None,
) -> bytes:
    """Erzeugt ein RFC-5545-konformes VEVENT als bytes.

    ``start``/``end`` als ``datetime`` ⇒ zeitgebundenes Event (timezone-aware
    Pflicht). Als ``date`` ⇒ ganztägiges Event (DTSTART/DTEND als DATE-only).

    Bei ganztägigen Mehrtages-Events ist ``end`` nach RFC 5545 *exklusiv*: für
    einen Termin von Mo–Fr ist ``start=Mo``, ``end=Sa``. Diese Funktion
    übernimmt das Datum **wie übergeben** – die Korrektur muss am Aufrufer
    erfolgen, weil dort die fachliche Semantik liegt.
    """
    if isinstance(start, datetime) and start.tzinfo is None:
        raise ValueError('start muss timezone-aware sein (z.B. ZoneInfo("Europe/Berlin"))')
    if isinstance(end, datetime) and end.tzinfo is None:
        raise ValueError('end muss timezone-aware sein')
    if method not in (METHOD_REQUEST, METHOD_CANCEL, METHOD_PUBLISH):
        raise ValueError(f'Ungültige Methode: {method!r}')

    cal = Calendar()
    cal.add('prodid', ICS_PRODID)
    cal.add('version', '2.0')
    cal.add('method', method)
    cal.add('calscale', 'GREGORIAN')

    event = Event()
    event.add('uid', uid)
    event.add('summary', summary)
    event.add('dtstart', start)
    event.add('dtend', end)
    event.add('dtstamp', datetime.now(tz=BERLIN))
    event.add('sequence', sequence)
    event.add('status', 'CANCELLED' if method == METHOD_CANCEL else 'CONFIRMED')

    if description:
        event.add('description', description)
    if location:
        event.add('location', location)
    if url:
        event.add('url', url)

    if organizer_email:
        organizer = vCalAddress(f'mailto:{organizer_email}')
        organizer.params['cn'] = vText('Ausbildungsmanagement')
        event['organizer'] = organizer

    for email in attendee_emails or []:
        if not email:
            continue
        attendee = vCalAddress(f'mailto:{email}')
        attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
        attendee.params['PARTSTAT'] = vText('NEEDS-ACTION')
        attendee.params['RSVP'] = vText('TRUE')
        event.add('attendee', attendee, encode=0)

    cal.add_component(event)
    return cal.to_ical()


def ics_attachment_tuple(
    filename: str,
    ics_bytes: bytes,
    method: str = METHOD_REQUEST,
) -> tuple[str, bytes, str]:
    """Verpackt ICS-bytes in das von ``services.email.send_mail`` erwartete Tupel.

    Der ``method``-Parameter im MIME-Type ist der entscheidende Trigger, der
    Outlook das Attachment als Termin-Einladung (mit „Annehmen"-Button)
    statt als generische Datei darstellen lässt.
    """
    mimetype = f'text/calendar; method={method}; charset=UTF-8; name="{filename}"'
    return (filename, ics_bytes, mimetype)


def daterange_end_exclusive(end_date: date) -> date:
    """Konvertiert ein inklusives Enddatum (fachlich) in das exklusive Enddatum (RFC 5545).

    Beispiel: Stationseinsatz „bis einschließlich 31.05." → DTEND=01.06.
    """
    from datetime import timedelta
    return end_date + timedelta(days=1)