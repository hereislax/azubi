# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
URL configuration for Azubi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views, logout as auth_logout
from django.conf import settings
from django.views.static import serve
from django.shortcuts import redirect
from .views import (
    index as index_view, impressum as impressum_view, datenschutz as datenschutz_view,
    barrierefreiheit as barrierefreiheit_view,
    acknowledgments as acknowledgments_view, global_search as global_search_view,
    auswertungen as auswertungen_view, dashboard_config_save as dashboard_config_save_view,
    report_detail as report_detail_view,
    report_export as report_export_view,
    saved_view_save as saved_view_save_view,
    saved_view_open as saved_view_open_view,
    saved_view_delete as saved_view_delete_view,
    custom_report_builder as custom_report_builder_view,
    custom_report_delete as custom_report_delete_view,
    healthz as healthz_view,
    readyz as readyz_view,
)
from django.views.decorators.http import require_POST
from services.views import (
    sso_error as sso_error_view,
    AzubiLoginView,
    sso_start as sso_start_view,
    login_otp as login_otp_view,
)


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'

urlpatterns = [
    # Health-/Readiness-Endpunkte (öffentlich, ohne Login) — beide Schreibweisen
    # registrieren, damit weder K8s/Prometheus noch Tools mit Trailing-Slash-Pflicht
    # einen 301-Redirect bekommen.
    path("healthz", healthz_view, name="healthz"),
    path("healthz/", healthz_view),
    path("readyz", readyz_view, name="readyz"),
    path("readyz/", readyz_view),

    path("", index_view, name="index"),
    path("dashboard/config/", dashboard_config_save_view, name="dashboard_config_save"),
    path("suche/", global_search_view, name="global_search"),
    path("auswertungen/", auswertungen_view, name="auswertungen"),
    path("auswertungen/builder/", custom_report_builder_view, name="custom_report_create"),
    path("auswertungen/builder/<int:pk>/", custom_report_builder_view, name="custom_report_edit"),
    path("auswertungen/builder/<int:pk>/loeschen/", custom_report_delete_view, name="custom_report_delete"),
    path("auswertungen/sicht/<int:pk>/", saved_view_open_view, name="saved_view_open"),
    path("auswertungen/sicht/<int:pk>/loeschen/", saved_view_delete_view, name="saved_view_delete"),
    path("auswertungen/<slug:slug>/", report_detail_view, name="report_detail"),
    path("auswertungen/<slug:slug>/sicht-speichern/", saved_view_save_view, name="saved_view_save"),
    path("auswertungen/<slug:slug>/export/<str:fmt>/", report_export_view, name="report_export"),
    path("impressum/", impressum_view, name="impressum"),
    path("datenschutz/", datenschutz_view, name="datenschutz"),
    path("barrierefreiheit/", barrierefreiheit_view, name="barrierefreiheit"),
    path("acknowledgments/", acknowledgments_view, name="acknowledgments"),
    path("", include("services.urls")),
    path("student/", include("student.urls")),
    path("kurs/", include("course.urls")),
    path("vortrag/", include("course.public_urls")),
    path("dokumente/", include("document.urls")),
    path("wohnheim/", include("dormitory.urls")),
    path("organisation/", include("organisation.urls")),
    path("praxistutoren/", include("instructor.urls")),
    path("ausbildungsnachweise/", include("proofoftraining.urls")),
    path("auditlog/", include("auditlog.urls")),
    path("portal/", include("portal.urls")),
    path("lerntage/", include("studyday.urls")),
    path("inventar/", include("inventory.urls")),
    path("abwesenheiten/", include("absence.urls")),
    path("beurteilungen/", include("assessment.urls")),
    path("massnahmen/", include("intervention.urls")),
    path("ankuendigungen/", include("announcements.urls")),
    path("wissensdatenbank/", include("knowledge.urls", namespace="knowledge")),
    path("raumbuchung/", include("workspace.urls")),
    path("pflichtschulungen/", include("mandatorytraining.urls")),
    path("workflows/", include("workflow.urls")),
    path("accounts/logout/", logout_view, name="logout"),
    # Eigene Login-View VOR django.contrib.auth.urls einbinden, damit unsere
    # Variante mit SSO-Buttons + Smart-Redirect statt der Default-View greift.
    path('accounts/login/', AzubiLoginView.as_view(), name='login'),
    # Zweiter Login-Schritt bei aktiviertem 2FA: nimmt User-PK aus Session
    # entgegen, prüft TOTP-/Recovery-Code und schließt den Login ab.
    path('accounts/login-otp/', login_otp_view, name='login_otp'),
    path('accounts/', include('django.contrib.auth.urls')),
    # Kleines Sprungbrett: setzt die Last-IdP-Cookie und leitet zum allauth-
    # OIDC-Login weiter. Login-Buttons zeigen nicht direkt auf /sso/oidc/...,
    # damit die Cookie-Logik garantiert greift.
    path('sso/start/<str:provider_id>/', sso_start_view, name='sso_start'),
    # SSO-Fehlerseite muss VOR der allauth-Inkludierung stehen, damit der
    # konkrete Pfad gewinnt. Adapter-Redirects landen hier.
    path('sso/fehler/', sso_error_view, name='sso_error'),
    # allauth unter /sso/, NICHT unter /accounts/ – sonst überschreibt es das
    # bestehende Login-/Reset-Setup. Wir nutzen aktuell nur die OIDC-Provider-
    # URLs (z.B. /sso/oidc/<provider_id>/login/[callback/]).
    path('sso/', include('allauth.urls')),
    path("admin/", admin.site.urls),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]
