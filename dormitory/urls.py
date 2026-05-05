# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = "dormitory"

urlpatterns = [
    path("", views.dormitory_list, name="dormitory_list"),
    path("<uuid:public_id>/", views.dormitory_detail, name="dormitory_detail"),
    path("zimmer/<uuid:public_id>/", views.room_detail, name="room_detail"),
    path("reservierung/neu/", views.assignment_create, name="assignment_create"),
    path("reservierung/neu/<uuid:room_public_id>/", views.assignment_create, name="assignment_create_for_room"),
    path("reservierung/<uuid:public_id>/bearbeiten/", views.assignment_edit, name="assignment_edit"),
    path("reservierung/<uuid:public_id>/entfernen/", views.assignment_delete, name="assignment_delete"),
    path("reservierung/<uuid:public_id>/confirmation/", views.confirmation_loading, name="confirmation_loading"),
    path("reservierung/<uuid:public_id>/confirmation/generate/", views.confirmation_generate, name="confirmation_generate"),

    path("calendar/", views.occupancy_calendar, name="occupancy_calendar"),

    path("sperrung/neu/", views.block_create, name="block_create"),
    path("sperrung/neu/<uuid:room_public_id>/", views.block_create, name="block_create_for_room"),
    path("sperrung/<uuid:public_id>/bearbeiten/", views.block_edit, name="block_edit"),
    path("sperrung/<uuid:public_id>/entfernen/", views.block_delete, name="block_delete"),
]
