# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('kalender/', views.coordinator_calendar, name='coordinator_calendar'),
    path('export/', views.student_export_csv, name='student_export_csv'),
    path('statistik/', views.student_statistics, name='student_statistics'),
    path('neu/', views.student_create, name='student_create'),
    path('datenschutz/', views.data_privacy_overview, name='data_privacy'),
    path('datenschutz/alle-anonymisieren/', views.anonymize_all, name='anonymize_all'),
    path('importieren/', views.student_import, name='student_import'),
    path('importieren/vorlage/', views.student_import_template, name='student_import_template'),
    path('dokumentvorlagen/<int:template_pk>/felder/', views.student_document_template_fields, name='student_document_template_fields'),
    path('<str:pk>/', views.student_detail, name='student_detail'),
    path('<str:pk>/bearbeiten/', views.student_edit, name='student_edit'),
    path('<str:pk>/set-status/', views.student_set_status, name='student_set_status'),
    path('<str:pk>/anonymisieren/', views.anonymize_student_view, name='anonymize_student'),
    path('<str:pk>/akte/hochladen/', views.student_document_upload, name='student_document_upload'),
    path('<str:pk>/akte/generieren/<int:template_pk>/', views.student_document_generate, name='student_document_generate'),
    path('<str:student_pk>/noten/neu/', views.grade_create, name='grade_create'),
    path('<str:student_pk>/noten/<uuid:grade_public_id>/bearbeiten/', views.grade_edit, name='grade_edit'),
    path('<str:student_pk>/noten/<uuid:grade_public_id>/entfernen/', views.grade_delete, name='grade_delete'),
    path('<str:pk>/kontakte/neu/', views.contact_entry_create, name='contact_entry_create'),
    path('<str:pk>/kontakte/<int:entry_pk>/loeschen/', views.contact_entry_delete, name='contact_entry_delete'),
    path('<str:pk>/checklisten/neu/', views.checklist_create, name='checklist_create'),
    path('<str:pk>/checklisten/<uuid:checklist_public_id>/loeschen/', views.checklist_delete, name='checklist_delete'),
    path('<str:pk>/checklisten/<uuid:checklist_public_id>/punkte/<uuid:item_public_id>/toggle/', views.checklist_item_toggle, name='checklist_item_toggle'),
    path('<str:pk>/notizen/neu/', views.internal_note_create, name='internal_note_create'),
    path('<str:pk>/notizen/<uuid:note_public_id>/loeschen/', views.internal_note_delete, name='internal_note_delete'),
    path('<str:pk>/notizen/<uuid:note_public_id>/anpinnen/', views.internal_note_toggle_pin, name='internal_note_toggle_pin'),
    path('<str:pk>/ausbildungsplan/<uuid:requirement_public_id>/toggle/', views.curriculum_toggle_completion, name='curriculum_toggle_completion'),
    path('<str:pk>/kompetenzmatrix/', views.student_competence_matrix, name='competence_matrix'),
]
