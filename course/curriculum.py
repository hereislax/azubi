# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Soll-Ist-Abgleich: Ausbildungsplan-Matching-Logik."""
from datetime import date

from .models import (
    CurriculumRequirement, CurriculumCompletion,
    InternshipAssignment, ASSIGNMENT_STATUS_APPROVED,
)


def get_curriculum_status(student):
    """
    Gibt für jede CurriculumRequirement des Berufsbilds den Erfüllungsstatus zurück.

    Returns:
        list[dict] mit Keys:
            requirement, status ('completed'|'in_progress'|'missing'),
            matching_assignments, total_days, required_days, percent,
            manually_completed (bool), completion (CurriculumCompletion|None)
    """
    try:
        job_profile = student.course.job_profile
    except AttributeError:
        return []

    requirements = list(
        CurriculumRequirement.objects
        .filter(job_profile=job_profile)
        .select_related('target_competence')
        .prefetch_related('target_units')
    )
    if not requirements:
        return []

    assignments = list(
        InternshipAssignment.objects
        .filter(student=student, status=ASSIGNMENT_STATUS_APPROVED)
        .select_related('unit')
        .prefetch_related('unit__competences')
    )

    # Manuelle Bestätigungen laden
    completions = {
        c.requirement_id: c
        for c in CurriculumCompletion.objects.filter(
            student=student,
            requirement__in=requirements,
        ).select_related('completed_by')
    }

    today = date.today()
    result = []

    for req in requirements:
        # Manuelle Bestätigung prüfen
        completion = completions.get(req.pk)

        target_unit_pks = set(req.target_units.values_list('pk', flat=True))
        has_specific_units = bool(target_unit_pks)

        matching = []
        total_days = 0

        for a in assignments:
            matched = False
            if has_specific_units:
                matched = a.unit_id in target_unit_pks
            elif req.target_competence_id:
                matched = a.unit.competences.filter(pk=req.target_competence_id).exists()

            if matched:
                matching.append(a)
                total_days += (a.end_date - a.start_date).days + 1

        required_days = req.min_duration_weeks * 7
        percent = min(100, int(total_days / required_days * 100)) if required_days else 100

        if completion:
            status = 'completed'
            percent = 100
        elif total_days >= required_days:
            status = 'completed'
        elif total_days > 0 or any(a.start_date <= today <= a.end_date for a in matching):
            status = 'in_progress'
        else:
            status = 'missing'

        result.append({
            'requirement': req,
            'status': status,
            'matching_assignments': matching,
            'total_days': total_days,
            'required_days': required_days,
            'percent': percent,
            'manually_completed': bool(completion),
            'completion': completion,
        })

    return result


def get_course_curriculum_overview(course):
    """
    Batch-optimierter Soll-Ist-Abgleich für alle Studenten eines Kurses.
    """
    from student.models import Student

    try:
        job_profile = course.job_profile
    except AttributeError:
        return {'requirements': [], 'students': []}

    requirements = list(
        CurriculumRequirement.objects
        .filter(job_profile=job_profile)
        .select_related('target_competence')
        .prefetch_related('target_units')
    )
    if not requirements:
        return {'requirements': [], 'students': []}

    students = list(
        Student.objects
        .filter(course=course, anonymized_at__isnull=True)
        .order_by('last_name', 'first_name')
    )

    all_assignments = list(
        InternshipAssignment.objects
        .filter(student__course=course, status=ASSIGNMENT_STATUS_APPROVED)
        .select_related('unit')
        .prefetch_related('unit__competences')
    )

    assignments_by_student = {}
    for a in all_assignments:
        assignments_by_student.setdefault(a.student_id, []).append(a)

    # Manuelle Bestätigungen batch-laden
    all_completions = CurriculumCompletion.objects.filter(
        student__in=students, requirement__in=requirements,
    )
    completion_set = {(c.student_id, c.requirement_id) for c in all_completions}

    # Target-Unit-PKs und Competence-Unit-PKs vorberechnen
    req_target_pks = []
    req_competence_unit_pks = []
    for req in requirements:
        pks = set(req.target_units.values_list('pk', flat=True))
        req_target_pks.append(pks)
        if not pks and req.target_competence_id:
            comp_pks = set(
                req.target_competence.units.values_list('pk', flat=True)
            )
        else:
            comp_pks = set()
        req_competence_unit_pks.append(comp_pks)

    student_rows = []

    for student in students:
        student_assignments = assignments_by_student.get(student.pk, [])
        statuses = []
        completed_count = 0
        total_mandatory = 0

        for i, req in enumerate(requirements):
            target_pks = req_target_pks[i]
            comp_pks = req_competence_unit_pks[i]
            has_specific = bool(target_pks)
            is_manually_done = (student.pk, req.pk) in completion_set

            total_days = 0
            for a in student_assignments:
                matched = False
                if has_specific:
                    matched = a.unit_id in target_pks
                elif comp_pks:
                    matched = a.unit_id in comp_pks
                if matched:
                    total_days += (a.end_date - a.start_date).days + 1

            required_days = req.min_duration_weeks * 7
            if is_manually_done or total_days >= required_days:
                status = 'completed'
            elif total_days > 0:
                status = 'in_progress'
            else:
                status = 'missing'

            statuses.append(status)

            if req.is_mandatory:
                total_mandatory += 1
                if status == 'completed':
                    completed_count += 1

        overall_percent = int(completed_count / total_mandatory * 100) if total_mandatory else 100

        student_rows.append({
            'student': student,
            'statuses': statuses,
            'overall_percent': overall_percent,
            'completed_count': completed_count,
            'total_mandatory': total_mandatory,
        })

    return {
        'requirements': requirements,
        'students': student_rows,
    }
