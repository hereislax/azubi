# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import AbsenceSettings, VacationConfirmationTemplate

admin.site.register(AbsenceSettings)
admin.site.register(VacationConfirmationTemplate)
