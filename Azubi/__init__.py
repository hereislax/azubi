# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from .celery import app as celery_app

__all__ = ('celery_app',)
