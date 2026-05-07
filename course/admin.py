# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin

from course.models import (
    Course, JobProfile, Career, Specialization, ScheduleBlock, GradeType,
    BlockLetterTemplate, InternshipPlanTemplate, StationLetterTemplate,
    CurriculumRequirement, CompetenceTarget,
)


class ScheduleBlockInline(admin.TabularInline):
    model = ScheduleBlock
    extra = 1


class CourseAdmin(admin.ModelAdmin):
    inlines = [ScheduleBlockInline]


admin.site.register(Course, CourseAdmin)


class GradeTypeInline(admin.TabularInline):
    model = GradeType
    extra = 1
    fields = ['name', 'order']


class CurriculumRequirementInline(admin.TabularInline):
    model = CurriculumRequirement
    extra = 1
    fields = ['order', 'name', 'target_competence', 'is_mandatory', 'min_duration_weeks']


class CompetenceTargetInline(admin.TabularInline):
    model = CompetenceTarget
    extra = 1
    fields = ['competence', 'target_value']
    autocomplete_fields = ('competence',)


class JobProfileAdmin(admin.ModelAdmin):
    inlines = [GradeTypeInline, CurriculumRequirementInline, CompetenceTargetInline]


admin.site.register(JobProfile, JobProfileAdmin)
admin.site.register(Career)
admin.site.register(Specialization)


@admin.register(BlockLetterTemplate)
class BlockLetterTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'job_profile', 'is_active', 'uploaded_at']
    list_editable = ['is_active']
    list_filter = ['job_profile', 'is_active']
    fields = ['name', 'job_profile', 'description', 'template_file', 'is_active']


@admin.register(InternshipPlanTemplate)
class InternshipPlanTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'job_profile', 'is_active', 'uploaded_at']
    list_editable = ['is_active']
    list_filter = ['job_profile', 'is_active']
    fields = ['name', 'job_profile', 'description', 'template_file', 'is_active']


@admin.register(StationLetterTemplate)
class StationLetterTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'job_profile', 'is_active', 'uploaded_at']
    list_editable = ['is_active']
    list_filter = ['job_profile', 'is_active']
    fields = ['name', 'job_profile', 'description', 'template_file', 'is_active']
