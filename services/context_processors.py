# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Template-Kontextvariablen, die in jeder Seite verfügbar sind."""
from services.roles import (
    is_training_coordinator, is_training_director, is_training_office,
    get_chief_instructor, is_dormitory_management, is_travel_expense_office,
    is_training_responsible, get_training_office_profile,
)


def site_config(request):
    """Stellt die globale Seitenkonfiguration und Modulflags bereit."""
    from django.conf import settings
    from services.models import SiteConfiguration
    app_version = getattr(settings, 'APP_VERSION', '')
    try:
        config = SiteConfiguration.get()
        return {
            'brand_name': config.brand_name or 'azubi.',
            'brand_header': config.brand_header or 'Eine offizielle Anwendung der Abteilung X in der Bundesbehörde Z',
            'brand_primary_color': config.brand_primary_color or '#0d6efd',
            'app_version': app_version,
            'module_dormitory':       config.module_dormitory,
            'module_inventory':       config.module_inventory,
            'module_absence':         config.module_absence,
            'module_studyday':        config.module_studyday,
            'module_assessment':      config.module_assessment,
            'module_intervention':    config.module_intervention,
            'module_announcements':   config.module_announcements,
            'module_knowledge':       config.module_knowledge,
            'module_proofoftraining': config.module_proofoftraining,
            'module_auditlog':        config.module_auditlog,
        }
    except Exception:
        return {
            'brand_name': 'azubi.',
            'brand_header': 'Eine offizielle Anwendung der Abteilung X in der Bundesbehörde Z',
            'brand_primary_color': '#0d6efd',
            'app_version': app_version,
            'module_dormitory': True, 'module_inventory': True, 'module_absence': True,
            'module_studyday': True, 'module_assessment': True, 'module_intervention': True,
            'module_announcements': True, 'module_knowledge': True,
            'module_proofoftraining': True, 'module_auditlog': True,
        }


def roles(request):
    """Stellt Rollen-Flags und zugehörige Profile für die aktuelle Sitzung bereit."""
    is_coordinator = request.user.is_authenticated and is_training_coordinator(request.user)
    is_director = request.user.is_authenticated and (
        is_training_director(request.user) or request.user.is_staff
    )
    is_office = request.user.is_authenticated and is_training_office(request.user)
    pending_tasks = _get_pending_tasks() if (is_director or is_office) else []
    student_profile = getattr(request.user, 'student_profile', None) if request.user.is_authenticated else None

    # Ungelesene Benachrichtigungen für Verwaltungsbenutzer laden
    unread_notifications = 0
    recent_notifications = []
    if request.user.is_authenticated and not student_profile:
        try:
            from services.models import Notification
            unread_qs = Notification.objects.filter(
                user=request.user, read_at__isnull=True
            ).order_by('-created_at')
            unread_notifications = unread_qs.count()
            recent_notifications = list(unread_qs[:5])
        except Exception:
            pass

    # Ungelesene Ankündigungen für Nachwuchskräfte zählen
    unread_announcements_count = 0
    if request.user.is_authenticated and student_profile:
        try:
            from announcements.models import AnnouncementRecipient, STATUS_PUBLISHED
            unread_announcements_count = AnnouncementRecipient.objects.filter(
                user=request.user,
                announcement__status=STATUS_PUBLISHED,
                read_at__isnull=True,
            ).count()
        except Exception:
            pass

    # Ausbildungsreferat-Profil für individuelle Zuständigkeiten
    training_office_profile = get_training_office_profile(request.user) if is_office and not is_director else None
    training_office_show_all = request.session.get('training_office_show_all', False) if is_office else False

    return {
        # Rollen-Flags
        'is_training_coordinator': is_coordinator,
        'is_training_director': is_director,
        'is_training_office': is_office,
        'is_dormitory_management': request.user.is_authenticated and is_dormitory_management(request.user),
        'is_travel_expense_office': request.user.is_authenticated and is_travel_expense_office(request.user),
        'is_training_responsible': request.user.is_authenticated and is_training_responsible(request.user),
        'chief_instructor_profile': get_chief_instructor(request.user) if is_coordinator else None,
        'pending_tasks': pending_tasks,
        'pending_tasks_count': len(pending_tasks),
        'student_profile': student_profile,
        'unread_notifications': unread_notifications,
        'recent_notifications': recent_notifications,
        'unread_announcements_count': unread_announcements_count,
        # Ausbildungsreferat-Profil und Zuständigkeitsflags
        'training_office_profile': training_office_profile,
        'training_office_show_all': training_office_show_all,
        # Berechtigungs-Flags (Leitung hat immer alle Rechte)
        'training_office_can_manage_dormitory': is_director or (training_office_profile and training_office_profile.can_manage_dormitory),
        'training_office_can_manage_inventory': is_director or (training_office_profile and training_office_profile.can_manage_inventory),
        'training_office_can_manage_absences': is_director or (training_office_profile and training_office_profile.can_manage_absences),
        'training_office_can_approve_vacation': is_director or (training_office_profile and training_office_profile.can_approve_vacation),
        'training_office_can_approve_study_days': is_director or (training_office_profile and training_office_profile.can_approve_study_days),
        'training_office_can_manage_announcements': is_director or (training_office_profile and training_office_profile.can_manage_announcements),
        'training_office_can_manage_interventions': is_director or (training_office_profile and training_office_profile.can_manage_interventions),
        # Abwärtskompatibilität: Alte Variablennamen
        'is_ausbildungsleitung': is_director,
        'is_ausbildungsreferat': is_office,
        'is_ausbildungskoordination': is_coordinator,
        'is_hausverwaltung': request.user.is_authenticated and is_dormitory_management(request.user),
        'is_reisekostenstelle': request.user.is_authenticated and is_travel_expense_office(request.user),
        'is_ausbildungsverantwortliche': request.user.is_authenticated and is_training_responsible(request.user),
        'referat_profile': training_office_profile,
        'referat_show_all': training_office_show_all,
        'referat_can_manage_dormitory': is_director or (training_office_profile and training_office_profile.can_manage_dormitory),
        'referat_can_manage_inventory': is_director or (training_office_profile and training_office_profile.can_manage_inventory),
        'referat_can_manage_absences': is_director or (training_office_profile and training_office_profile.can_manage_absences),
        'referat_can_approve_vacation': is_director or (training_office_profile and training_office_profile.can_approve_vacation),
        'referat_can_approve_study_days': is_director or (training_office_profile and training_office_profile.can_approve_study_days),
        'referat_can_manage_announcements': is_director or (training_office_profile and training_office_profile.can_manage_announcements),
        'referat_can_manage_interventions': is_director or (training_office_profile and training_office_profile.can_manage_interventions),
    }


def _get_pending_tasks():
    """Sammelt alle offenen Aufgaben für die Ausbildungsleitung."""
    from django.urls import reverse
    tasks = []

    # ── Beurteilungen bestätigen ───────────────────────────────────────────
    try:
        from assessment.models import Assessment, STATUS_SUBMITTED
        assessment_qs = (
            Assessment.objects
            .filter(status=STATUS_SUBMITTED)
            .select_related('assignment__student', 'assignment__unit', 'assignment__schedule_block')
            .order_by('submitted_at')
        )
        for a in assessment_qs:
            tasks.append({
                'icon': 'bi-clipboard-check',
                'category': 'Beurteilung bestätigen',
                'label': f'{a.assignment.student.first_name} {a.assignment.student.last_name} – {a.assignment.unit.name}',
                'sub': f'{a.assignment.start_date.strftime("%d.%m.%Y")} – {a.assignment.end_date.strftime("%d.%m.%Y")}',
                'url': reverse('assessment:detail', kwargs={'public_id': a.public_id}),
            })
    except Exception:
        pass

    # ── Zuweisungsschreiben freigeben ───────────────────────────────────────
    from course.models import BlockLetter, BLOCK_LETTER_STATUS_PENDING
    letter_qs = (
        BlockLetter.objects
        .filter(status=BLOCK_LETTER_STATUS_PENDING)
        .select_related('schedule_block__course')
        .order_by('generated_at')
    )
    for letter in letter_qs:
        block = letter.schedule_block
        url = reverse(
            'course:block_letter_approve',
            kwargs={'course_pk': block.course_id, 'block_pk': block.pk, 'letter_pk': letter.pk},
        )
        tasks.append({
            'icon': 'bi-envelope-check',
            'category': 'Zuweisungsschreiben freigeben',
            'label': block.name,
            'sub': f'{block.course_id} · erstellt von {letter.generated_by.get_full_name() or (letter.generated_by.username if letter.generated_by else "–")}',
            'url': url,
        })

    # ── Praktikumspläne freigeben ───────────────────────────────────────────
    from course.models import InternshipPlanLetter, StationLetter
    for plan in (
        InternshipPlanLetter.objects
        .filter(status=BLOCK_LETTER_STATUS_PENDING)
        .select_related('schedule_block__course', 'generated_by')
        .order_by('generated_at')
    ):
        block = plan.schedule_block
        tasks.append({
            'icon': 'bi-map',
            'category': 'Praktikumsplan freigeben',
            'label': block.name,
            'sub': f'{block.course_id} · erstellt von {plan.generated_by.get_full_name() or (plan.generated_by.username if plan.generated_by else "–")}',
            'url': reverse('course:internship_plan_approve', kwargs={'course_pk': block.course_id, 'block_pk': block.pk, 'letter_pk': plan.pk}),
        })

    # ── Stationsschreiben freigeben ─────────────────────────────────────────
    for sl in (
        StationLetter.objects
        .filter(status=BLOCK_LETTER_STATUS_PENDING)
        .select_related('schedule_block__course', 'generated_by')
        .order_by('generated_at')
    ):
        block = sl.schedule_block
        tasks.append({
            'icon': 'bi-building-check',
            'category': 'Stationsschreiben freigeben',
            'label': block.name,
            'sub': f'{block.course_id} · erstellt von {sl.generated_by.get_full_name() or (sl.generated_by.username if sl.generated_by else "–")}',
            'url': reverse('course:station_letter_approve', kwargs={'course_pk': block.course_id, 'block_pk': block.pk, 'letter_pk': sl.pk}),
        })

    # ── Änderungsanträge genehmigen ──────────────────────────────────────
    from course.models import AssignmentChangeRequest, CHANGE_REQUEST_STATUS_PENDING
    from django.urls import reverse as _reverse
    cr_qs = (
        AssignmentChangeRequest.objects
        .filter(status=CHANGE_REQUEST_STATUS_PENDING)
        .select_related('assignment__student', 'assignment__unit', 'requested_by')
        .order_by('requested_at')
    )
    for cr in cr_qs:
        a = cr.assignment
        requester = cr.requested_by.get_full_name() or cr.requested_by.username if cr.requested_by else '–'
        tasks.append({
            'icon': 'bi-pencil-square',
            'category': 'Änderungsantrag',
            'label': f'{a.student.first_name} {a.student.last_name} – {a.unit.name}',
            'sub': f'{cr.get_change_type_display()}: {cr.summary()} · beantragt von {requester}',
            'url': _reverse('instructor:change_request_review', kwargs={'change_request_public_id': cr.public_id}),
        })

    # ── Ausbildungsnachweise prüfen ────────────────────────────────────────
    from proofoftraining.models import TrainingRecord, STATUS_SUBMITTED
    proof_qs = (
        TrainingRecord.objects
        .filter(status=STATUS_SUBMITTED)
        .select_related('student')
        .order_by('submitted_at')
    )
    for rec in proof_qs:
        from django.urls import reverse as _rev
        tasks.append({
            'icon': 'bi-journal-check',
            'category': 'Ausbildungsnachweis prüfen',
            'label': f'{rec.student.first_name} {rec.student.last_name}',
            'sub': f'KW {rec.calendar_week}/{rec.week_start.year} · eingereicht {rec.submitted_at.strftime("%d.%m.%Y")}',
            'url': _rev('proofoftraining:admin_record_detail',
                        kwargs={'student_pk': rec.student.pk, 'pk': rec.pk}),
        })

    # ── Praxistutoren bestätigen ────────────────────────────────────────────
    from instructor.models import Instructor, INSTRUCTOR_STATUS_PENDING
    instructor_qs = (
        Instructor.objects
        .filter(status=INSTRUCTOR_STATUS_PENDING)
        .select_related('unit')
        .order_by('last_name', 'first_name')
    )
    for inst in instructor_qs:
        url = reverse('instructor:instructor_confirm', kwargs={'public_id': inst.public_id})
        tasks.append({
            'icon': 'bi-person-check',
            'category': 'Praxistutor bestätigen',
            'label': f'{inst.first_name} {inst.last_name}',
            'sub': inst.unit.name if inst.unit else '–',
            'url': url,
        })

    return tasks
