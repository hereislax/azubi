# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'absence'

urlpatterns = [
    # ── Urlaubsanträge (Ausbildungsreferat) ───────────────────────────────────
    path('urlaub/', views.vacation_list, name='vacation_list'),
    path('urlaub/neu/', views.vacation_create, name='vacation_create'),
    path('urlaub/<uuid:public_id>/', views.vacation_detail, name='vacation_detail'),
    path('urlaub/<uuid:public_id>/entscheiden/', views.vacation_decide, name='vacation_decide'),
    path('urlaub/<uuid:public_id>/stornieren/', views.vacation_cancel_create, name='vacation_cancel_create'),
    path('urlaub/<uuid:public_id>/signiert/', views.vacation_signed_pdf, name='vacation_signed_pdf'),

    # ── Krankmeldungen (Ausbildungsreferat) ───────────────────────────────────
    path('krank/', views.sick_leave_list, name='sick_leave_list'),
    path('krank/neu/', views.sick_leave_create, name='sick_leave_create'),
    path('krank/<uuid:public_id>/schliessen/', views.sick_leave_close, name='sick_leave_close'),

    # ── Urlaubsstelle-Portal (kein Login erforderlich) ────────────────────────
    path('urlaubsstelle/<uuid:token>/', views.urlaubsstelle_portal, name='urlaubsstelle_portal'),
    path('urlaubsstelle/<uuid:token>/abgeschlossen/', views.urlaubsstelle_done, name='urlaubsstelle_done'),

    # ── Einstellungen ─────────────────────────────────────────────────────────
    path('einstellungen/', views.absence_settings, name='absence_settings'),

]
