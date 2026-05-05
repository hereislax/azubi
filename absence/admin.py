# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import (
    AbsenceSettings, VacationRequest, VacationBatch,
    VacationConfirmationTemplate, SickLeave, StudentAbsenceState,
)

admin.site.register(AbsenceSettings)
admin.site.register(VacationRequest)
admin.site.register(VacationBatch)
admin.site.register(VacationConfirmationTemplate)
admin.site.register(SickLeave)
admin.site.register(StudentAbsenceState)
