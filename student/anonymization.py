# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from datetime import date, timedelta
from django.utils import timezone
from services.paperless import PaperlessService

def anonymize_student(student) -> bool:
    """
    Anonymisiert einen Studierenden: löscht Paperless-Dokumente und
    überschreibt persönliche Daten mit anonymen Platzhaltern.
    """

    # Paperless-Dokumente löschen
    docs = PaperlessService.get_documents_for_student(student.pk)
    for doc in docs:
        PaperlessService.delete_document(doc['id'])

    # Persönliche Daten anonymisieren
    student.first_name = "Anonym"
    student.last_name = "Anonym"
    student.date_of_birth = date(1900, 1, 1)
    student.place_of_birth = ""
    student.phone_number = ""
    student.email_private = "anonym@anonym.de"
    student.email_id = "anonym@anonym.de"

    student.anonymized_at = timezone.now()
    student.save()

    # Adresse löschen
    if student.address:
        old_address = student.address
        student.address = None
        student.save(update_fields=['address'])
        old_address.delete()

    # Benutzerdefinierte Feldwerte löschen
    student.custom_field_values.all().delete()

    # Paperless-Bestätigungs-IDs bei Zimmerzuweisungen löschen
    student.room_assignments.update(paperless_confirmation_id=None)

    return True

def _get_anonymization_months():
    try:
        from services.models import SiteConfiguration
        return SiteConfiguration.get().anonymization_months
    except Exception:
        return 12


def get_students_due_for_anonymization():
    """
    Gibt Studierende zurück, die anonymisiert werden müssen:
    - noch nicht anonymisiert
    - Status != 'aktiv'
    - Status wurde vor mehr als `anonymization_months` Monaten geändert
    """
    from .models import Student

    months = _get_anonymization_months()
    cutoff = timezone.now() - timedelta(days=months * 30)
    return Student.objects.filter(
        anonymized_at__isnull=True,
        status_changed_at__isnull=False,
        status_changed_at__lt=cutoff,
    ).exclude(
        status__description__in=['aktiv']
    ).select_related('status')


def get_students_approaching_anonymization():
    """
    Gibt Studierende zurück, die sich der Anonymisierungsfrist nähern
    (letztes Zehntel der konfigurierten Frist).
    """
    from .models import Student

    months = _get_anonymization_months()
    now = timezone.now()
    cutoff_due = now - timedelta(days=months * 30)
    # "Approaching" = letztes Zehntel der Frist (mindestens 14 Tage)
    approach_days = max(int(months * 30 * 0.1), 14)
    cutoff_warn = now - timedelta(days=months * 30 - approach_days)
    return Student.objects.filter(
        anonymized_at__isnull=True,
        status_changed_at__isnull=False,
        status_changed_at__gte=cutoff_due,
        status_changed_at__lt=cutoff_warn,
    ).exclude(
        status__description__in=['aktiv']
    ).select_related('status')
