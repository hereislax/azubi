# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import (
    AssessmentCriterion, AssessmentTemplate, AssessmentTemplateCriterion,
    StationFeedbackCategory, CriterionCompetenceWeight,
)


class AssessmentTemplateCriterionInline(admin.TabularInline):
    model = AssessmentTemplateCriterion
    extra = 1
    fields = ('criterion', 'order')


class CriterionCompetenceWeightInline(admin.TabularInline):
    model = CriterionCompetenceWeight
    extra = 1
    fields = ('competence', 'weight')
    autocomplete_fields = ('competence',)


@admin.register(AssessmentCriterion)
class AssessmentCriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_profile', 'category', 'order', 'competence_count')
    list_filter = ('job_profile', 'category')
    search_fields = ('name', 'job_profile__job_profile')
    ordering = ('job_profile', 'order', 'name')
    inlines = [CriterionCompetenceWeightInline]

    @admin.display(description='Kompetenzen')
    def competence_count(self, obj):
        return obj.competences.count()


@admin.register(AssessmentTemplate)
class AssessmentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_profile', 'rating_scale', 'active')
    list_filter = ('job_profile', 'rating_scale', 'active')
    inlines = [AssessmentTemplateCriterionInline]


@admin.register(StationFeedbackCategory)
class StationFeedbackCategoryAdmin(admin.ModelAdmin):
    list_display = ('label', 'name', 'order', 'active')
    list_editable = ('order', 'active')
    ordering = ('order', 'name')
