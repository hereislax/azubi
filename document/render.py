# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Renderer für Word-Dokumente und Wrapper für Paperless-Upload.

Domänen-Views nutzen ``render_docx(...)`` um eine .docx-Vorlage mit
einem Context zu rendern und ``upload_to_paperless(...)`` um das
Ergebnis in die Akte abzulegen. So bleibt die docxtpl-Abhängigkeit
und Paperless-Integration an einer Stelle.
"""
from __future__ import annotations

from io import BytesIO


def render_docx(template_path: str, context: dict) -> bytes:
    """Rendert eine .docx-Vorlage mit dem gegebenen Context.

    Wirft die zugrundeliegende ``Exception`` weiter, damit der Aufrufer
    eine View-spezifische Fehlermeldung produzieren kann.
    """
    from docxtpl import DocxTemplate
    doc = DocxTemplate(template_path)
    doc.render(context)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def upload_to_paperless(
    *,
    file_bytes: bytes,
    title: str,
    filename: str,
    student_id: str | None = None,
    document_type: str | None = None,
    mime_type: str = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
) -> int | None:
    """Lädt ein generiertes Dokument in Paperless und gibt die doc_id zurück.

    Wenn ``student_id`` gesetzt ist, wird die NK-spezifische
    ``upload_and_wait``-Variante verwendet (verknüpft das Dokument mit
    der Akte). Sonst die generische ``upload_and_wait_simple``.

    Setzt das Ausfertigungsdatum (``created``) anschließend auf den
    heutigen Tag, damit Paperless' OCR-Datumserkennung nicht
    versehentlich z.B. ein Geburts- oder Kursdatum aus dem Vorlagen-
    Inhalt übernimmt.
    """
    from datetime import date
    from services.paperless import PaperlessService
    if student_id:
        doc_id = PaperlessService.upload_and_wait(
            file_bytes=file_bytes,
            title=title,
            student_id=student_id,
            filename=filename,
            mime_type=mime_type,
        )
    else:
        kwargs = {
            'file_bytes': file_bytes,
            'title': title,
            'filename': filename,
            'mime_type': mime_type,
        }
        if document_type:
            kwargs['document_type'] = document_type
        doc_id = PaperlessService.upload_and_wait_simple(**kwargs)

    if doc_id is not None:
        PaperlessService.update_document(doc_id, created=date.today().isoformat())
    return doc_id