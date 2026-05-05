# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Smoke-Tests für die document-App."""
from django.apps import apps


def test_app_loaded():
    """App ist registriert und AppConfig lädt."""
    assert apps.get_app_config("document") is not None


def test_models_importable():
    """Models-Modul lädt ohne ImportError."""
    from document import models  # noqa: F401
