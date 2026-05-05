# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""URL-Konfiguration für die Services-App: Dokumentenverwaltung, Einstellungen, Konten und Benachrichtigungen."""
from django.urls import path

from services.views import (
    assign_document, document_inbox, document_update, paperless_preview_proxy, paperless_search,
    paperless_search_course, paperless_settings, smtp_settings,
    account_management, account_edit, account_toggle_active,
    settings_overview, settings_content,
    settings_templates, settings_appearance, settings_system, settings_tasks, settings_modules,
    theme_css, favicon_svg, logo_svg, logo_text_svg, manifest_json, sw_js,
    notifications_list, notification_mark_read, notification_preferences,
    toggle_training_office_scope, mein_konto,
    backup_dashboard, backup_list, backup_settings, backup_trigger, backup_delete,
)

app_name = "services"

urlpatterns = [
    path("inbox/", document_inbox, name="inbox"),
    path("dokumente/<int:paperless_doc_id>/vorschau/", paperless_preview_proxy, name="paperless_preview"),
    path("dokumente/<int:paperless_doc_id>/zuweisen/", assign_document, name="assign_document"),
    path("dokumente/<int:paperless_doc_id>/bearbeiten/", document_update, name="document_update"),
    # URL-Pfad bleibt deutsch für Benutzer, interner Name wird umbenannt
    path("referat/scope/", toggle_training_office_scope, name="toggle_training_office_scope"),
    path("konten/", account_management, name="account_management"),
    path("konten/<int:user_pk>/bearbeiten/", account_edit, name="account_edit"),
    path("konten/<int:user_pk>/aktiv/", account_toggle_active, name="account_toggle_active"),
    path("student/<str:student_pk>/akte/suche/", paperless_search, name="paperless_search"),
    path("kurs/<str:course_pk>/akte/suche/", paperless_search_course, name="paperless_search_course"),
    # Settings
    path("einstellungen/", settings_overview, name="settings_overview"),
    path("einstellungen/smtp/", smtp_settings, name="smtp_settings"),
    path("einstellungen/paperless/", paperless_settings, name="paperless_settings"),
    path("einstellungen/seiteninhalte/", settings_content, name="settings_content"),
    path("einstellungen/vorlagen/", settings_templates, name="settings_templates"),
    path("einstellungen/erscheinungsbild/", settings_appearance, name="settings_appearance"),
    path("einstellungen/systeminfo/", settings_system, name="settings_system"),
    path("einstellungen/aufgaben/", settings_tasks, name="settings_tasks"),
    path("einstellungen/module/", settings_modules, name="settings_modules"),
    # Backup-UI (Stufe 4) – nur Superuser
    path("einstellungen/backup/",                            backup_dashboard, name="backup_dashboard"),
    path("einstellungen/backup/dateien/",                    backup_list,      name="backup_list"),
    path("einstellungen/backup/konfiguration/",              backup_settings,  name="backup_settings"),
    path("einstellungen/backup/aktion/<str:action>/",        backup_trigger,   name="backup_trigger"),
    path("einstellungen/backup/loeschen/<str:filename>/",    backup_delete,    name="backup_delete"),
    path("theme.css", theme_css, name="theme_css"),
    path("favicon.svg", favicon_svg, name="favicon_svg"),
    path("logo.svg", logo_svg, name="logo_svg"),
    path("logo-text.svg", logo_text_svg, name="logo_text_svg"),
    path("manifest.json", manifest_json, name="manifest_json"),
    path("sw.js", sw_js, name="sw_js"),
]

# Diese URLs werden direkt auf der Root-Ebene eingebunden (via path("", include("services.urls")))
from django.urls import path as _path
urlpatterns += [
    _path("benachrichtigungen/", notifications_list, name="notifications"),
    _path("benachrichtigungen/<int:pk>/lesen/", notification_mark_read, name="notification_mark_read"),
    _path("benachrichtigungen/praeferenzen/", notification_preferences, name="notification_preferences"),
    _path("mein-konto/", mein_konto, name="mein_konto"),
]
