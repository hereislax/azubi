# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Smoke-Tests für die portal-App."""
from django.apps import apps


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("portal") is not None


def test_views_importable():
    """Views-Modul lädt ohne ImportError (portal hat keine models.py)."""
    from portal import views  # noqa: F401
