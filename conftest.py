# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Globale pytest-Fixtures für das Azubi-Portal."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def user(db):
    """Standard-User ohne besondere Rechte."""
    return get_user_model().objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )


@pytest.fixture
def admin_user(db):
    """Superuser für Admin-Views."""
    return get_user_model().objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def client_logged_in(client, user):
    """Test-Client mit eingeloggtem Standard-User."""
    client.force_login(user)
    return client


@pytest.fixture
def client_admin(client, admin_user):
    """Test-Client mit eingeloggtem Superuser."""
    client.force_login(admin_user)
    return client


@pytest.fixture
def api_client():
    """Frischer, unauthentisierter Client."""
    return Client()