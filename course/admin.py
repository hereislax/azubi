# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin

from course.models import (
    Course, JobProfile, Career, Specialization, ScheduleBlock, InternshipAssignment, GradeType,
    BlockLetterTemplate, InternshipPlanTemplate, StationLetterTemplate,
    CourseChecklist, CourseChecklistItem,
    CurriculumRequirement, CompetenceTarget,
    SeminarLecture,
)


class ScheduleBlockInline(admin.TabularInline):
    model = ScheduleBlock
    extra = 1


class CourseAdmin(admin.ModelAdmin):
    inlines = [ScheduleBlockInline]


admin.site.register(Course, CourseAdmin)
admin.site.register(InternshipAssignment)
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


@admin.register(CurriculumRequirement)
class CurriculumRequirementAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_profile', 'is_mandatory', 'min_duration_weeks', 'order')
    list_filter = ('job_profile', 'is_mandatory')
    filter_horizontal = ('target_units',)
    fields = ('job_profile', 'name', 'description', 'target_competence', 'target_units',
              'min_duration_weeks', 'is_mandatory', 'order')


@admin.register(CompetenceTarget)
class CompetenceTargetAdmin(admin.ModelAdmin):
    list_display = ('competence', 'job_profile', 'target_value')
    list_filter = ('job_profile',)
    list_editable = ('target_value',)
    autocomplete_fields = ('competence',)
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


class CourseChecklistItemInline(admin.TabularInline):
    model = CourseChecklistItem
    extra = 0
    fields = ['order', 'text', 'completed', 'completed_by', 'completed_at']
    readonly_fields = ['completed_at']


@admin.register(CourseChecklist)
class CourseChecklistAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'template', 'created_by', 'created_at']
    list_filter = ['course']
    inlines = [CourseChecklistItemInline]


@admin.register(SeminarLecture)
class SeminarLectureAdmin(admin.ModelAdmin):
    list_display = ['topic', 'speaker_name', 'start_datetime', 'end_datetime', 'status', 'schedule_block']
    list_filter = ['status', 'schedule_block__course']
    search_fields = ['topic', 'speaker_name', 'speaker_email']
    readonly_fields = ['public_id', 'confirmation_token', 'sent_at', 'responded_at',
                       'reminder_sent_at', 'notification_sequence', 'created_at', 'updated_at']
