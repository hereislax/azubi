# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'course'

urlpatterns = [
    path('', views.course_list, name='course_list'),
    # Berufsbild-Konfiguration (Kriterien + Endziele für Kompetenzmatrix)
    path('berufsbild/', views.job_profile_list, name='job_profile_list'),
    path('berufsbild/<int:pk>/', views.job_profile_config, name='job_profile_config'),
    path('berufsbild/<int:profile_pk>/kriterien/neu/', views.criterion_create, name='criterion_create'),
    path('berufsbild/<int:profile_pk>/kriterien/<int:pk>/bearbeiten/', views.criterion_edit, name='criterion_edit'),
    path('berufsbild/<int:profile_pk>/kriterien/<int:pk>/entfernen/', views.criterion_delete, name='criterion_delete'),
    path('berufsbild/<int:profile_pk>/endziele/neu/', views.competence_target_create, name='competence_target_create'),
    path('berufsbild/<int:profile_pk>/endziele/<int:pk>/bearbeiten/', views.competence_target_edit, name='competence_target_edit'),
    path('berufsbild/<int:profile_pk>/endziele/<int:pk>/entfernen/', views.competence_target_delete, name='competence_target_delete'),
    path('neu/', views.course_create, name='course_create'),
    path('kapazitaet/', views.capacity_planning, name='capacity_planning'),
    path('kalender/', views.course_calendar, name='course_calendar'),
    path('<str:pk>/ausbildungsplan/', views.curriculum_overview, name='curriculum_overview'),
    path('<str:pk>/kompetenzmatrix/', views.course_competence_matrix, name='course_competence_matrix'),
    path('<str:pk>/', views.course_detail, name='course_detail'),
    path('<str:pk>/bearbeiten/', views.course_edit, name='course_edit'),
    path('<str:pk>/checklisten/anlegen/', views.course_checklist_bulk_create, name='course_checklist_bulk_create'),
    path('<str:pk>/kurs-checklisten/neu/', views.course_checklist_create, name='course_checklist_create'),
    path('<str:pk>/kurs-checklisten/<int:checklist_pk>/entfernen/', views.course_checklist_delete, name='course_checklist_delete'),
    path('<str:pk>/kurs-checklisten/<int:checklist_pk>/punkt/<int:item_pk>/toggle/', views.course_checklist_item_toggle, name='course_checklist_item_toggle'),
    path('<str:pk>/akte/hochladen/', views.course_document_upload, name='course_document_upload'),
    path('<str:pk>/entfernen/', views.course_delete, name='course_delete'),
    path('<str:course_pk>/ablaufplan/neu/', views.schedule_block_create, name='schedule_block_create'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/bearbeiten/', views.schedule_block_edit, name='schedule_block_edit'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/entfernen/', views.schedule_block_delete, name='schedule_block_delete'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikum/', views.internship_calendar, name='internship_calendar'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/vorschlaege/', views.internship_suggestions, name='internship_suggestions'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikum/neu/', views.internship_assignment_create, name='internship_assignment_create'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikum/<str:assignment_pk>/bearbeiten/', views.internship_assignment_edit, name='internship_assignment_edit'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikum/<str:assignment_pk>/entfernen/', views.internship_assignment_delete, name='internship_assignment_delete'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/zuweisungsschreiben/neu/', views.block_letter_create, name='block_letter_create'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/zuweisungsschreiben/<int:letter_pk>/', views.block_letter_detail, name='block_letter_detail'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/zuweisungsschreiben/<int:letter_pk>/generieren/', views.block_letter_generate, name='block_letter_generate'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/zuweisungsschreiben/<int:letter_pk>/freigeben/', views.block_letter_approve, name='block_letter_approve'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/zuweisungsschreiben/<int:letter_pk>/eintrag/<int:item_pk>/neu-erstellen/', views.block_letter_item_regenerate, name='block_letter_item_regenerate'),
    # Praktikumspläne
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikumsplan/neu/', views.internship_plan_create, name='internship_plan_create'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikumsplan/<int:letter_pk>/', views.internship_plan_detail, name='internship_plan_detail'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikumsplan/<int:letter_pk>/generieren/', views.internship_plan_generate, name='internship_plan_generate'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikumsplan/<int:letter_pk>/freigeben/', views.internship_plan_approve, name='internship_plan_approve'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/praktikumsplan/<int:letter_pk>/eintrag/<int:item_pk>/neu-erstellen/', views.internship_plan_item_regenerate, name='internship_plan_item_regenerate'),
    # Stationszuweisungsschreiben
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/stationsschreiben/neu/', views.station_letter_create, name='station_letter_create'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/stationsschreiben/<int:letter_pk>/', views.station_letter_detail, name='station_letter_detail'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/stationsschreiben/<int:letter_pk>/generieren/', views.station_letter_generate, name='station_letter_generate'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/stationsschreiben/<int:letter_pk>/freigeben/', views.station_letter_approve, name='station_letter_approve'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/stationsschreiben/<int:letter_pk>/eintrag/<int:item_pk>/neu-erstellen/', views.station_letter_item_regenerate, name='station_letter_item_regenerate'),
    # Seminar / Vortragsplanung
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/seminar/', views.seminar_calendar, name='seminar_calendar'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/seminar/vortrag/neu/', views.lecture_create, name='lecture_create'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/seminar/vortrag/<uuid:lecture_public_id>/bearbeiten/', views.lecture_edit, name='lecture_edit'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/seminar/vortrag/<uuid:lecture_public_id>/entfernen/', views.lecture_delete, name='lecture_delete'),
    path('<str:course_pk>/ablaufplan/<uuid:block_public_id>/seminar/export/', views.seminar_plan_export, name='seminar_plan_export'),
]
