# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = "organisation"

urlpatterns = [
    path("", views.unit_list, name="unit_list"),
    path("neu/", views.unit_create, name="unit_create"),
    path("import/", views.unit_import, name="unit_import"),
    path("import/vorlage/", views.unit_import_template, name="unit_import_template"),
    path("<uuid:public_id>/", views.unit_detail, name="unit_detail"),
    path("<uuid:public_id>/bearbeiten/", views.unit_edit, name="unit_edit"),
    path("<uuid:public_id>/entfernen/", views.unit_delete, name="unit_delete"),
    path("standorte/", views.location_list, name="location_list"),
    path("standorte/neu/", views.location_create, name="location_create"),
    path("standorte/<uuid:public_id>/bearbeiten/", views.location_edit, name="location_edit"),
    path("standorte/<uuid:public_id>/entfernen/", views.location_delete, name="location_delete"),
    path("kompetenzen/", views.competence_list, name="competence_list"),
    path("kompetenzen/neu/", views.competence_create, name="competence_create"),
    path("kompetenzen/<uuid:public_id>/bearbeiten/", views.competence_edit, name="competence_edit"),
    path("kompetenzen/<uuid:public_id>/entfernen/", views.competence_delete, name="competence_delete"),
]
