# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.home, name='home'),
    path('daten/', views.daten, name='daten'),
    path('stationsplan/', views.stationsplan, name='stationsplan'),
    path('noten/', views.noten, name='noten'),
    path('lerntage/', views.studyday_list, name='studyday_list'),
    path('lerntage/neu/', views.studyday_create, name='studyday_create'),

    # ── Urlaub ────────────────────────────────────────────────────────────────
    path('urlaub/', views.vacation_list, name='vacation_list'),
    path('urlaub/neu/', views.vacation_create, name='vacation_create'),
    path('urlaub/<uuid:public_id>/stornieren/', views.vacation_cancel, name='vacation_cancel'),

    # ── Selbstbeurteilung ─────────────────────────────────────────────────────
    path('beurteilung/<str:assignment_id>/', views.beurteilung_self, name='beurteilung_self'),
    path('beurteilung/<str:assignment_id>/fremdbeurteilung/', views.beurteilung_view, name='beurteilung_view'),

    # ── Anonyme Stationsbewertung ─────────────────────────────────────────────
    path('stationsbewertung/<str:assignment_id>/', views.station_feedback, name='station_feedback'),

    # ── Kalender ──────────────────────────────────────────────────────────────
    path('kalender/', views.kalender, name='kalender'),

    # ── Wissensdatenbank ──────────────────────────────────────────────────────
    path('wissensdatenbank/', views.kb_list, name='kb_list'),
    path('wissensdatenbank/<uuid:public_id>/', views.kb_detail, name='kb_detail'),

    # ── Ankündigungen ──────────────────────────────────────────────────────────
    path('ankuendigungen/', views.announcement_list, name='announcement_list'),
    path('ankuendigungen/<uuid:public_id>/', views.announcement_detail, name='announcement_detail'),
    path('ankuendigungen/<uuid:public_id>/bestaetigen/', views.announcement_acknowledge, name='acknowledge'),

    # ── Einsatzwünsche ─────────────────────────────────────────────────────
    path('einsatzwuensche/', views.einsatzwuensche, name='einsatzwuensche'),

    # ── Ausbildungsplan ─────────────────────────────────────────────────────
    path('ausbildungsplan/', views.ausbildungsplan, name='ausbildungsplan'),
    path('kompetenzmatrix/', views.kompetenzmatrix, name='kompetenzmatrix'),

    # ── Dokumente (Generierung) ─────────────────────────────────────────────
    path('dokumente/', views.dokumente, name='dokumente'),
    path('dokumente/generieren/<int:template_pk>/', views.dokument_generieren, name='dokument_generieren'),

    # ── Persönliche Daten bearbeiten ─────────────────────────────────────────
    path('daten/bearbeiten/', views.daten_bearbeiten, name='daten_bearbeiten'),
]
