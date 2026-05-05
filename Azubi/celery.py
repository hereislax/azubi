# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Azubi.settings')

app = Celery('Azubi')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()