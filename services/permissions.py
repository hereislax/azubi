# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Zentrale Berechtigungs-Helfer für Studierenden-Zugriff.

Spiegelt die Zugriffslogik aus ``student.views.student_detail`` wider und
ist für alle anderen Views gedacht, die einen Studierenden per ID laden
und prüfen müssen, ob der angemeldete Benutzer ihn sehen darf.
"""
from datetime import date, timedelta

from django.db.models import Q

from .roles import (
    is_training_director, is_training_office, is_training_coordinator,
    is_training_responsible, is_dormitory_management, is_travel_expense_office,
    get_chief_instructor, get_dormitory_management_profile,
    get_training_office_profile,
)


def user_can_access_student(user, student) -> bool:
    """True, wenn ``user`` auf die Akte von ``student`` zugreifen darf."""
    if not user.is_authenticated:
        return False

    if user.is_staff or is_training_director(user):
        return True

    if is_training_office(user):
        profile = get_training_office_profile(user)
        if not profile:
            return True
        jp_pks = list(profile.job_profiles.values_list('pk', flat=True))
        if not jp_pks:
            return True
        return bool(student.course and student.course.job_profile_id in jp_pks)

    if is_travel_expense_office(user):
        return True

    if is_training_responsible(user):
        from student.models import TrainingResponsibleAccess
        if TrainingResponsibleAccess.objects.filter(
            user=user, student=student,
        ).exists():
            return True

    if is_training_coordinator(user):
        chief = get_chief_instructor(user)
        if chief and chief.coordination:
            from instructor.views import _get_coordination_area
            from course.models import InternshipAssignment
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)
            cutoff = date.today() - timedelta(days=14)
            if InternshipAssignment.objects.filter(
                student=student,
                unit_id__in=descendant_pks,
                end_date__gte=cutoff,
            ).exists():
                return True

    if is_dormitory_management(user):
        profile = get_dormitory_management_profile(user)
        if profile:
            from dormitory.models import RoomAssignment as DormRoomAssignment
            cutoff = date.today() + timedelta(days=90)
            return DormRoomAssignment.objects.filter(
                student=student,
                room__dormitory=profile.dormitory,
                start_date__lte=cutoff,
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=date.today())
            ).exists()

    if hasattr(user, 'student_profile'):
        return user.student_profile.pk == student.pk

    return False