# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
import requests as http_requests
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def _require_document_access(user, paperless_id):
    """Verweigert Zugriff, wenn ``user`` das Paperless-Dokument nicht sehen darf."""
    from services.paperless import PaperlessService
    from services.permissions import user_can_access_student
    from services.roles import is_training_director, is_training_office
    from student.models import Student

    if user.is_staff or is_training_director(user):
        return

    correspondent_name = PaperlessService.get_correspondent_name_for_document(paperless_id)
    if correspondent_name:
        student = Student.objects.filter(pk=correspondent_name).first()
        if student and user_can_access_student(user, student):
            return
        if student:
            raise PermissionDenied

    # Kein Studierenden-Korrespondent (Kursdokument o. unzugewiesen):
    # nur Leitung/Staff (oben bereits behandelt) und Referat dürfen zugreifen.
    if is_training_office(user):
        return
    raise PermissionDenied


@login_required
def document_preview(request, paperless_id):
    """Wrapper page: shows PDF preview in iframe + download-original button."""
    _require_document_access(request.user, paperless_id)
    from services.paperless import PaperlessService
    title = PaperlessService.get_document_title(paperless_id) or "Dokument"
    return render(request, "document/document_preview.html", {
        "paperless_id": paperless_id,
        "document_title": title,
    })


@login_required
def document_download_original(request, paperless_id):
    """Proxies the original file download from Paperless-ngx."""
    _require_document_access(request.user, paperless_id)
    try:
        from services.paperless import PaperlessService
        resp = http_requests.get(
            f"{PaperlessService._base()}/api/documents/{paperless_id}/download/",
            headers=PaperlessService._headers(),
            params={"original": "true"},
            timeout=30,
            stream=True,
        )
        resp.raise_for_status()
        response = HttpResponse(
            resp.content,
            content_type=resp.headers.get("Content-Type", "application/octet-stream"),
        )
        response["Content-Disposition"] = resp.headers.get(
            "Content-Disposition", "attachment; filename=document.docx"
        )
        return response
    except http_requests.RequestException:
        raise Http404("Original file not available.")