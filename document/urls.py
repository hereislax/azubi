# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = "document"

urlpatterns = [
    path("documents/<int:paperless_id>/preview/", views.document_preview, name="document_preview"),
    path("documents/<int:paperless_id>/download-original/", views.document_download_original, name="document_download_original"),
]
