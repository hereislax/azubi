# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    # Übersicht
    path("", views.inventory_list, name="inventory_list"),

    # Schnell-Ausgabe per Scan/Seriennummer
    path("schnell-ausgabe/", views.quick_issue, name="quick_issue"),

    # Excel-Import
    path("import/", views.inventory_import, name="inventory_import"),
    path("import/vorlage/", views.inventory_import_template, name="inventory_import_template"),

    # QR-Code & Etiketten
    path("gegenstand/<uuid:public_id>/qr.png", views.item_qr_image, name="item_qr_image"),
    path("gegenstand/<uuid:public_id>/etikett/", views.item_label, name="item_label"),
    path("etiketten/", views.labels_print, name="labels_print"),

    # Kategorien
    path("kategorien/", views.category_list, name="category_list"),
    path("kategorien/neu/", views.category_create, name="category_create"),
    path("kategorien/<uuid:public_id>/bearbeiten/", views.category_edit, name="category_edit"),
    path("kategorien/<uuid:public_id>/loeschen/", views.category_delete, name="category_delete"),

    # Gegenstände
    path("gegenstand/neu/", views.item_create, name="item_create"),
    path("gegenstand/<uuid:public_id>/", views.item_detail, name="item_detail"),
    path("gegenstand/<uuid:public_id>/bearbeiten/", views.item_edit, name="item_edit"),
    path("gegenstand/<uuid:public_id>/loeschen/", views.item_delete, name="item_delete"),

    # Ausgaben
    path("gegenstand/<uuid:item_public_id>/ausgabe/", views.issuance_create, name="issuance_create"),
    path("ausgabe/<uuid:public_id>/rueckgabe/", views.issuance_return, name="issuance_return"),
    path("ausgabe/<uuid:public_id>/quittung/", views.issuance_receipt_download, name="issuance_receipt_download"),
    path("scan-verarbeiten/", views.scan_upload, name="scan_upload"),

    # Vorlagen
    path("vorlagen/", views.template_list, name="template_list"),
    path("vorlagen/neu/", views.template_create, name="template_create"),
    path("vorlagen/<uuid:public_id>/bearbeiten/", views.template_edit, name="template_edit"),
    path("vorlagen/<uuid:public_id>/loeschen/", views.template_delete, name="template_delete"),
]
