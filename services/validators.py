# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Gemeinsame Validierungsfunktionen für Datei-Uploads.
"""
from django.core.exceptions import ValidationError

# Erlaubte Erweiterungen pro Dateityp
DOCX_EXTENSIONS   = {'docx'}
PDF_EXTENSIONS    = {'pdf'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'doc', 'xlsx', 'csv', 'jpg', 'jpeg', 'png'}

# Größenlimits
MAX_TEMPLATE_SIZE  = 20 * 1024 * 1024   # 20 MB für .docx-Vorlagen
MAX_SCAN_SIZE      = 50 * 1024 * 1024   # 50 MB für eingescannte PDFs
MAX_DOCUMENT_SIZE  = 50 * 1024 * 1024   # 50 MB für allgemeine Dokumente


def validate_file_upload(file, allowed_extensions: set[str], max_size: int, label: str = 'Datei'):
    """
    Prüft Dateiendung und Dateigröße eines hochgeladenen Uploads.

    Args:
        file:               InMemoryUploadedFile / TemporaryUploadedFile
        allowed_extensions: Menge erlaubter Dateiendungen (ohne Punkt, Kleinbuchstaben)
        max_size:           Maximale Dateigröße in Bytes
        label:              Anzeigename für Fehlermeldungen

    Raises:
        ValidationError: bei ungültiger Endung oder Überschreitung der Größe
    """
    if not file:
        return

    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''

    if ext not in allowed_extensions:
        erlaubt = ', '.join(sorted(f'.{e}' for e in allowed_extensions))
        raise ValidationError(
            f'{label}: Ungültiges Dateiformat „.{ext}". Erlaubt sind: {erlaubt}.'
        )

    if file.size > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise ValidationError(
            f'{label}: Die Datei ist zu groß (maximal {limit_mb} MB).'
        )


def validate_docx(file):
    """Kurzform für .docx-Vorlagen."""
    validate_file_upload(file, DOCX_EXTENSIONS, MAX_TEMPLATE_SIZE, 'Vorlage')


def validate_pdf(file):
    """Kurzform für eingescannte PDFs."""
    validate_file_upload(file, PDF_EXTENSIONS, MAX_SCAN_SIZE, 'PDF')


def validate_document(file):
    """Kurzform für allgemeine Dokumente (Kursakte, Anhänge)."""
    validate_file_upload(file, DOCUMENT_EXTENSIONS, MAX_DOCUMENT_SIZE, 'Dokument')
