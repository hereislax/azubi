# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import (
    AssessmentCriterion, AssessmentTemplate, AssessmentTemplateCriterion,
    Assessment, AssessmentRating, SelfAssessment, SelfAssessmentRating,
    StationFeedbackCategory, StationFeedback, StationFeedbackRating,
    CriterionCompetenceWeight,
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


class AssessmentRatingInline(admin.TabularInline):
    model = AssessmentRating
    extra = 0
    readonly_fields = ('criterion', 'value', 'comment')
    can_delete = False


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'assessor_name', 'status', 'submitted_at', 'confirmed_at')
    list_filter = ('status',)
    readonly_fields = (
        'token', 'token_sent_at', 'assessor_name', 'assessor_email',
        'submitted_at', 'confirmed_by', 'confirmed_at',
    )
    inlines = [AssessmentRatingInline]


class SelfAssessmentRatingInline(admin.TabularInline):
    model = SelfAssessmentRating
    extra = 0
    readonly_fields = ('criterion', 'value', 'comment')
    can_delete = False


@admin.register(SelfAssessment)
class SelfAssessmentAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'status', 'submitted_at')
    list_filter = ('status',)
    readonly_fields = ('submitted_at',)
    inlines = [SelfAssessmentRatingInline]


# ── Anonyme Stationsbewertung ─────────────────────────────────────────────────

@admin.register(StationFeedbackCategory)
class StationFeedbackCategoryAdmin(admin.ModelAdmin):
    list_display = ('label', 'name', 'order', 'active')
    list_editable = ('order', 'active')
    ordering = ('order', 'name')


class StationFeedbackRatingInline(admin.TabularInline):
    model = StationFeedbackRating
    extra = 0
    readonly_fields = ('category', 'value')
    can_delete = False


@admin.register(StationFeedback)
class StationFeedbackAdmin(admin.ModelAdmin):
    list_display = ('unit', 'schedule_block', 'submitted_at', 'average_grade')
    list_filter = ('unit', 'schedule_block')
    readonly_fields = ('unit', 'schedule_block', 'submitted_at', 'comment')
    inlines = [StationFeedbackRatingInline]

    def has_add_permission(self, request):
        return False  # Nur über das Portal erstellt
