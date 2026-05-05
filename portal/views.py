# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für das Nachwuchskräfte-Portal (Dashboard, Stammdaten, Urlaub, Lerntage, Nachrichten etc.)."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render


def _get_student_or_403(request):
    """Gibt das Nachwuchskraft-Profil des eingeloggten Nutzers zurück oder wirft 403."""
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        raise PermissionDenied
    return student


@login_required
def home(request):
    """Portal-Dashboard für die eingeloggte Nachwuchskraft."""
    student = _get_student_or_403(request)
    today = date.today()

    from course.models import InternshipAssignment, ASSIGNMENT_STATUS_APPROVED

    # Aktueller Einsatz
    current_assignment = (
        InternshipAssignment.objects
        .filter(student=student, status=ASSIGNMENT_STATUS_APPROVED,
                start_date__lte=today, end_date__gte=today)
        .select_related('unit', 'instructor', 'location', 'schedule_block__course')
        .first()
    )

    # Nächster zukünftiger Einsatz
    next_assignment = (
        InternshipAssignment.objects
        .filter(student=student, status=ASSIGNMENT_STATUS_APPROVED, start_date__gt=today)
        .select_related('unit', 'instructor', 'location', 'schedule_block__course')
        .order_by('start_date')
        .first()
    )

    # Ausbildungsnachweise (nur wenn Berufsbild es erfordert)
    requires_proof = False
    nachweis_open = None
    nachweis_counts = {}
    try:
        requires_proof = student.course.job_profile.requires_proof_of_training
    except AttributeError:
        pass

    if requires_proof:
        from proofoftraining.models import TrainingRecord
        nachweis_open = (
            TrainingRecord.objects
            .filter(student=student, status__in=['draft', 'rejected'])
            .order_by('-week_start')
            .first()
        )
        qs = TrainingRecord.objects.filter(student=student)
        nachweis_counts = {
            'approved':  qs.filter(status='approved').count(),
            'submitted': qs.filter(status='submitted').count(),
            'rejected':  qs.filter(status='rejected').count(),
            'draft':     qs.filter(status='draft').count(),
        }

    # Noten
    from student.models import Grade
    grades = (
        Grade.objects
        .filter(student=student)
        .select_related('grade_type')
        .order_by('grade_type__order', 'grade_type__name')
    )

    # Ausstehende Selbstbeurteilungen (Assignments ohne eingereichte SelfAssessment)
    pending_self_assessments = []
    try:
        from assessment.models import AssessmentTemplate, SelfAssessment, STATUS_SUBMITTED
        job_profile = student.course.job_profile
        if AssessmentTemplate.objects.filter(job_profile=job_profile, active=True).exists():
            completed_ids = SelfAssessment.objects.filter(
                assignment__student=student,
                status=STATUS_SUBMITTED,
            ).values_list('assignment_id', flat=True)
            pending_self_assessments = list(
                InternshipAssignment.objects
                .filter(student=student, status=ASSIGNMENT_STATUS_APPROVED)
                .exclude(pk__in=completed_ids)
                .filter(end_date__lte=today)
                .select_related('unit')
                .order_by('-end_date')[:5]
            )
    except Exception:
        pass

    # Kalender-Vorschau für aktuelle Jahresansicht im Dashboard
    cal_year = int(request.GET.get('cal_year', today.year))
    from student.calendar_utils import build_student_calendar
    calendar_preview = build_student_calendar(student, cal_year, portal_view=True)

    from django.urls import reverse
    nav_items = [
        {'url': reverse('portal:stationsplan'),         'icon': 'bi-geo-alt',         'label': 'Stationsplan'},
        {'url': reverse('portal:noten'),                'icon': 'bi-mortarboard',      'label': 'Noten'},
        {'url': reverse('portal:vacation_list'),        'icon': 'bi-calendar-check',   'label': 'Urlaub'},
        {'url': reverse('portal:studyday_list'),        'icon': 'bi-book',             'label': 'Lerntage'},
        {'url': reverse('portal:kalender'),             'icon': 'bi-calendar3',        'label': 'Mein Kalender'},
        {'url': reverse('portal:daten'),                'icon': 'bi-person-badge',     'label': 'Meine Daten'},
        {'url': reverse('portal:ausbildungsplan'),       'icon': 'bi-list-check',       'label': 'Ausbildungsplan'},
        {'url': reverse('portal:dokumente'),            'icon': 'bi-file-earmark-text','label': 'Bescheinigungen'},
        {'url': reverse('portal:nachrichten'),          'icon': 'bi-chat-left-text',   'label': 'Nachrichten'},
        {'url': reverse('portal:kb_list'),              'icon': 'bi-journal-bookmark', 'label': 'Wissensdatenbank'},
        {'url': reverse('portal:announcement_list'),    'icon': 'bi-megaphone',        'label': 'Ankündigungen'},
        {'url': reverse('proofoftraining:record_list') if requires_proof else '',
         'icon': 'bi-journal-text', 'label': 'Nachweise'},
    ]
    if not requires_proof:
        nav_items = [n for n in nav_items if n['label'] != 'Nachweise']

    # Ausbildungsfortschritt
    curriculum_progress = None
    try:
        if student.course and student.course.job_profile:
            from course.curriculum import get_curriculum_status
            cs = get_curriculum_status(student)
            mandatory = [r for r in cs if r['requirement'].is_mandatory]
            if mandatory:
                done = sum(1 for r in mandatory if r['status'] == 'completed')
                curriculum_progress = {'done': done, 'total': len(mandatory), 'pct': int(done / len(mandatory) * 100)}
    except Exception:
        pass

    # Ungelesene Ankündigungen
    from announcements.models import AnnouncementRecipient, STATUS_PUBLISHED
    unread_announcements = AnnouncementRecipient.objects.filter(
        user=request.user,
        announcement__status=STATUS_PUBLISHED,
        read_at__isnull=True,
    ).count()

    # Ungelesene Nachrichten (Anfragen mit neuen Staff-Antworten)
    from student.models import StudentInquiry
    unread_messages = 0
    for inq in StudentInquiry.objects.filter(student=student).prefetch_related('replies'):
        last_own = inq.replies.filter(is_staff_reply=False).order_by('-created_at').first()
        cutoff = last_own.created_at if last_own else inq.created_at
        if inq.replies.filter(is_staff_reply=True, created_at__gt=cutoff).exists():
            unread_messages += 1

    return render(request, 'portal/home.html', {
        'student': student,
        'today': today,
        'current_assignment': current_assignment,
        'next_assignment': next_assignment,
        'requires_proof': requires_proof,
        'nachweis_open': nachweis_open,
        'nachweis_counts': nachweis_counts,
        'grades': grades,
        'nav_items': nav_items,
        'pending_self_assessments': pending_self_assessments,
        'calendar_preview': calendar_preview,
        'unread_announcements': unread_announcements,
        'unread_messages': unread_messages,
        'curriculum_progress': curriculum_progress,
    })


@login_required
def daten(request):
    """Stammdaten der eingeloggten Nachwuchskraft (read-only)."""
    student = _get_student_or_403(request)

    from student.models import StudentFieldValue
    custom_fields = (
        StudentFieldValue.objects
        .filter(student=student)
        .select_related('field')
        .order_by('field__name')
    )

    return render(request, 'portal/daten.html', {
        'student': student,
        'custom_fields': custom_fields,
    })


@login_required
def stationsplan(request):
    """Alle Praktikumseinsätze der eingeloggten Nachwuchskraft."""
    student = _get_student_or_403(request)
    today = date.today()

    from course.models import InternshipAssignment, ASSIGNMENT_STATUS_APPROVED

    assignments = (
        InternshipAssignment.objects
        .filter(student=student)
        .select_related('unit', 'instructor', 'location', 'schedule_block__course')
        .prefetch_related('assessment', 'self_assessment')
        .order_by('start_date')
    )

    # Aufteilen in vergangen / aktuell / zukünftig
    past, current, upcoming = [], [], []
    for a in assignments:
        if a.end_date < today:
            past.append(a)
        elif a.start_date <= today <= a.end_date:
            current.append(a)
        else:
            upcoming.append(a)

    return render(request, 'portal/stationsplan.html', {
        'student': student,
        'today': today,
        'past': past,
        'current': current,
        'upcoming': upcoming,
    })


@login_required
def noten(request):
    """Noten der eingeloggten Nachwuchskraft (read-only)."""
    student = _get_student_or_403(request)

    from student.models import Grade
    grades = (
        Grade.objects
        .filter(student=student)
        .select_related('grade_type__job_profile')
        .order_by('grade_type__order', 'grade_type__name', '-date')
    )

    return render(request, 'portal/noten.html', {
        'student': student,
        'grades': grades,
    })


# ── Urlaub (Portal) ──────────────────────────────────────────────────────────

@login_required
def vacation_list(request):
    """Übersicht der eigenen Urlaubsanträge im Nachwuchskräfte-Portal."""
    student = _get_student_or_403(request)

    from absence.models import VacationRequest
    from absence.forms import VacationRequestPortalForm

    vacation_requests = (
        VacationRequest.objects
        .filter(student=student, is_cancellation=False)
        .prefetch_related('cancellation_requests')
        .order_by('-start_date')
    )
    form = VacationRequestPortalForm()

    return render(request, 'portal/vacation_list.html', {
        'student': student,
        'vacation_requests': vacation_requests,
        'form': form,
    })


@login_required
def vacation_create(request):
    """Nachwuchskraft stellt einen neuen Urlaubsantrag im Portal."""
    student = _get_student_or_403(request)

    if request.method != 'POST':
        return redirect('portal:vacation_list')

    from absence.forms import VacationRequestPortalForm
    from absence.models import VacationRequest

    form = VacationRequestPortalForm(request.POST)
    if form.is_valid():
        vr = form.save(commit=False)
        vr.student = student
        vr.submitted_via_portal = True
        vr.is_cancellation = False
        vr.save()
        try:
            from django.urls import reverse
            from services.models import notify_staff
            notify_staff(
                message=f'Urlaubsantrag eingereicht: {student.first_name} {student.last_name} '
                        f'({vr.start_date.strftime("%d.%m.%Y")}–{vr.end_date.strftime("%d.%m.%Y")})',
                link=reverse('absence:vacation_list'),
                icon='bi-calendar-check',
                category='Urlaub',
            )
        except Exception:
            pass
        messages.success(
            request,
            f'Ihr Urlaubsantrag ({vr.start_date.strftime("%d.%m.%Y")}–{vr.end_date.strftime("%d.%m.%Y")}) '
            f'wurde eingereicht und wird vom Ausbildungsreferat bearbeitet.',
        )
    else:
        for err in form.errors.values():
            messages.error(request, ', '.join(err))

    return redirect('portal:vacation_list')


@login_required
def vacation_cancel(request, public_id):
    """Nachwuchskraft stellt einen Stornierungsantrag für einen eigenen Urlaubsantrag."""
    student = _get_student_or_403(request)

    from absence.models import (
        VacationRequest, STATUS_APPROVED, STATUS_PROCESSED, STATUS_PENDING,
    )

    original = get_object_or_404(
        VacationRequest,
        public_id=public_id,
        student=student,
        is_cancellation=False,
    )

    if original.status not in (STATUS_APPROVED, STATUS_PROCESSED):
        messages.warning(request, 'Nur genehmigte Anträge können storniert werden.')
        return redirect('portal:vacation_list')

    existing = original.cancellation_requests.filter(
        status__in=(STATUS_PENDING, STATUS_APPROVED)
    ).first()
    if existing:
        messages.warning(request, 'Es existiert bereits ein offener Stornierungsantrag.')
        return redirect('portal:vacation_list')

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        VacationRequest.objects.create(
            student=student,
            start_date=original.start_date,
            end_date=original.end_date,
            is_cancellation=True,
            original_request=original,
            notes=notes,
            submitted_via_portal=True,
        )
        try:
            from django.urls import reverse
            from services.models import notify_staff
            notify_staff(
                message=f'Stornierungsantrag eingereicht: {student.first_name} {student.last_name} '
                        f'({original.start_date.strftime("%d.%m.%Y")}–{original.end_date.strftime("%d.%m.%Y")})',
                link=reverse('absence:vacation_list'),
                icon='bi-calendar-x',
                category='Urlaub',
            )
        except Exception:
            pass
        messages.success(
            request,
            'Ihr Stornierungsantrag wurde eingereicht und wird vom Ausbildungsreferat bearbeitet.',
        )
        return redirect('portal:vacation_list')

    return render(request, 'portal/vacation_cancel.html', {'original': original})


# ── Lern- und Studientage (Portal) ────────────────────────────────────────────

@login_required
def studyday_list(request):
    """Übersicht der Lerntag-Anträge mit aktuellem Guthaben."""
    student = _get_student_or_403(request)

    from studyday.models import StudyDayRequest, get_study_day_balance
    requests_qs = (
        StudyDayRequest.objects
        .filter(student=student)
        .order_by('-date')
    )
    balance = get_study_day_balance(student)

    return render(request, 'studyday/portal_list.html', {
        'student': student,
        'study_requests': requests_qs,
        'balance': balance,
    })


@login_required
def studyday_create(request):
    """Nachwuchskraft stellt einen neuen Lerntag-Antrag."""
    student = _get_student_or_403(request)

    from studyday.models import (
        StudyDayRequest, StudyDayBlackout,
        get_study_day_balance, STATUS_PENDING,
        TYPE_STUDY, TYPE_EXAM_PREP, WEEKDAY_LONG,
    )
    balance = get_study_day_balance(student)

    if balance is None:
        messages.error(
            request,
            'Für Ihr Berufsbild sind keine Lern- und Studientage hinterlegt. '
            'Bitte wenden Sie sich an das Ausbildungsreferat.',
        )
        return redirect('portal:studyday_list')

    policy = balance['policy']

    def _render_form(**extra):
        """Hilfsfunktion: rendert das Antragsformular mit Standard-Kontext."""
        ctx = {
            'student': student,
            'balance': balance,
            'policy': policy,
            'today': date.today().isoformat(),
            'min_date': (date.today() + __import__('datetime').timedelta(days=policy.min_advance_days)).isoformat(),
        }
        ctx.update(extra)
        return render(request, 'studyday/portal_create.html', ctx)

    if request.method == 'POST':
        date_str      = request.POST.get('date', '').strip()
        date_end_str  = request.POST.get('date_end', '').strip()
        reason        = request.POST.get('reason', '').strip()
        request_type  = request.POST.get('request_type', TYPE_STUDY)

        # Art validieren
        if request_type not in (TYPE_STUDY, TYPE_EXAM_PREP):
            request_type = TYPE_STUDY

        # Prüfungsvorbereitungstage: nur wenn Kontingent vorhanden
        if request_type == TYPE_EXAM_PREP and policy.exam_prep_days is None:
            request_type = TYPE_STUDY

        # Startdatum validieren
        try:
            requested_date = date.fromisoformat(date_str)
        except ValueError:
            messages.error(request, 'Bitte geben Sie ein gültiges Datum ein.')
            return _render_form(date_value=date_str, reason_value=reason, request_type=request_type)

        # Enddatum validieren (bei Mehrtagsanträgen)
        requested_date_end = None
        if policy.max_days_per_request > 1 and date_end_str:
            try:
                requested_date_end = date.fromisoformat(date_end_str)
                if requested_date_end < requested_date:
                    messages.error(request, 'Das Enddatum muss nach dem Startdatum liegen.')
                    return _render_form(date_value=date_str, date_end_value=date_end_str,
                                        reason_value=reason, request_type=request_type)
                days_requested = (requested_date_end - requested_date).days + 1
                if days_requested > policy.max_days_per_request:
                    messages.error(
                        request,
                        f'Pro Antrag können maximal {policy.max_days_per_request} aufeinanderfolgende Tage beantragt werden.',
                    )
                    return _render_form(date_value=date_str, date_end_value=date_end_str,
                                        reason_value=reason, request_type=request_type)
            except ValueError:
                messages.error(request, 'Bitte geben Sie ein gültiges Enddatum ein.')
                return _render_form(date_value=date_str, reason_value=reason, request_type=request_type)

        # Beantragungsfrist prüfen
        if policy.min_advance_days > 0:
            from datetime import timedelta
            earliest = date.today() + timedelta(days=policy.min_advance_days)
            if requested_date < earliest:
                messages.error(
                    request,
                    f'Anträge müssen mindestens {policy.min_advance_days} Tag(e) im Voraus eingereicht werden. '
                    f'Frühestmögliches Datum: {earliest.strftime("%d.%m.%Y")}.',
                )
                return _render_form(date_value=date_str, reason_value=reason, request_type=request_type)

        # Wochentag prüfen
        allowed_wd = policy.get_allowed_weekday_ints()
        if policy.allowed_weekdays and requested_date.weekday() not in allowed_wd:
            allowed_names = ', '.join(WEEKDAY_LONG[d] for d in sorted(allowed_wd) if 0 <= d <= 6)
            messages.error(
                request,
                f'Lern- und Studientage können nur an folgenden Tagen beantragt werden: {allowed_names}.',
            )
            return _render_form(date_value=date_str, reason_value=reason, request_type=request_type)

        # Sperrzeitraum prüfen (für gesamten beantragten Zeitraum)
        check_end = requested_date_end or requested_date
        blackouts = StudyDayBlackout.objects.filter(policy=policy)
        check = requested_date
        while check <= check_end:
            for bo in blackouts:
                if bo.is_in_period(check):
                    label = bo.label or 'gesperrter Zeitraum'
                    messages.error(
                        request,
                        f'Am {check.strftime("%d.%m.%Y")} können keine Lerntage beantragt werden ({label}).',
                    )
                    return _render_form(date_value=date_str, reason_value=reason, request_type=request_type)
            from datetime import timedelta
            check += timedelta(days=1)

        # Doppelter Antrag prüfen
        if StudyDayRequest.objects.filter(
            student=student,
            date=requested_date,
            status__in=[STATUS_PENDING, 'approved'],
        ).exists():
            messages.error(
                request,
                f'Für den {requested_date.strftime("%d.%m.%Y")} liegt bereits ein Antrag vor.',
            )
            return _render_form(date_value=date_str, reason_value=reason, request_type=request_type)

        # Restguthaben prüfen
        if request_type == TYPE_EXAM_PREP:
            ep = balance.get('exam_prep')
            if ep and ep['remaining'] <= 0:
                messages.error(
                    request,
                    'Ihr Prüfungsvorbereitungs-Kontingent für dieses Ausbildungsjahr ist aufgebraucht.',
                )
                return redirect('portal:studyday_list')
        else:
            remaining = balance['remaining']
            if balance.get('monthly_remaining') is not None:
                remaining = min(remaining, balance['monthly_remaining'])
            if remaining <= 0:
                messages.error(
                    request,
                    'Ihr Lern- und Studientage-Guthaben ist aufgebraucht. '
                    'Ein neuer Antrag ist nicht möglich.',
                )
                return redirect('portal:studyday_list')

        StudyDayRequest.objects.create(
            student=student,
            date=requested_date,
            date_end=requested_date_end,
            request_type=request_type,
            reason=reason,
            status=STATUS_PENDING,
        )
        try:
            from django.urls import reverse
            from services.models import notify_staff
            date_label = (
                f'{requested_date.strftime("%d.%m.%Y")}–{requested_date_end.strftime("%d.%m.%Y")}'
                if requested_date_end else requested_date.strftime('%d.%m.%Y')
            )
            notify_staff(
                message=f'Lerntag-Antrag eingereicht: {student.first_name} {student.last_name} – {date_label}',
                link=reverse('studyday:request_list'),
                icon='bi-book',
                category='Lerntag',
            )
        except Exception:
            pass
        messages.success(
            request,
            f'Ihr Antrag wurde eingereicht und wird vom Ausbildungsreferat bearbeitet.',
        )
        return redirect('portal:studyday_list')

    return _render_form()


# ── Selbstbeurteilung ─────────────────────────────────────────────────────────

@login_required
def kalender(request):
    """Kalenderansicht der eigenen Ausbildung im Portal."""
    student = _get_student_or_403(request)
    year = int(request.GET.get('year', date.today().year))
    from student.calendar_utils import build_student_calendar
    calendar_data = build_student_calendar(student, year, portal_view=True)
    return render(request, 'portal/kalender.html', {
        'student': student,
        'calendar_data': calendar_data,
    })


@login_required
def beurteilung_self(request, assignment_id):
    """Selbstbeurteilungsformular für Auszubildende im Portal."""
    student = _get_student_or_403(request)

    from course.models import InternshipAssignment
    assignment = get_object_or_404(
        InternshipAssignment,
        pk=assignment_id,
        student=student,
    )

    # Passende aktive Beurteilungsvorlage suchen
    from assessment.models import AssessmentTemplate, SelfAssessment, STATUS_SUBMITTED
    try:
        job_profile = student.course.job_profile
    except AttributeError:
        messages.error(request, 'Kein Berufsbild für dein Konto hinterlegt.')
        return redirect('portal:home')

    template = AssessmentTemplate.objects.filter(job_profile=job_profile, active=True).first()
    if not template:
        messages.info(request, 'Für dein Berufsbild ist keine Beurteilungsvorlage hinterlegt.')
        return redirect('portal:home')

    self_assessment, _ = SelfAssessment.objects.get_or_create(
        assignment=assignment,
        defaults={'template': template},
    )

    if request.method == 'POST' and self_assessment.status != STATUS_SUBMITTED:
        from assessment.forms import SelfAssessmentForm
        form = SelfAssessmentForm(self_assessment, request.POST)
        if form.is_valid():
            submit = (request.POST.get('action') == 'submit')
            form.save(submit=submit)
            if submit:
                messages.success(request, 'Selbstbeurteilung erfolgreich eingereicht.')
            else:
                messages.success(request, 'Entwurf gespeichert.')
            return redirect('portal:beurteilung_self', assignment_id=assignment_id)
    else:
        from assessment.forms import SelfAssessmentForm
        form = SelfAssessmentForm(self_assessment)

    return render(request, 'portal/beurteilung_self.html', {
        'student': student,
        'assignment': assignment,
        'template': template,
        'self_assessment': self_assessment,
        'form': form,
    })


@login_required
def station_feedback(request, assignment_id):
    """Anonymes Stationsbewertungsformular für Nachwuchskräfte."""
    student = _get_student_or_403(request)

    from course.models import InternshipAssignment
    assignment = get_object_or_404(
        InternshipAssignment,
        pk=assignment_id,
        student=student,
    )

    today = date.today()

    # Bewertung nur ab Beginn des Einsatzes möglich
    if assignment.start_date > today:
        messages.info(request, 'Die Stationsbewertung ist erst ab Beginn des Einsatzes möglich.')
        return redirect('portal:stationsplan')

    # Bereits abgegeben → Read-only-Seite
    if assignment.station_feedback_submitted:
        return render(request, 'portal/station_feedback_done.html', {
            'student': student,
            'assignment': assignment,
            'already_submitted': True,
        })

    from assessment.forms import StationFeedbackForm
    if request.method == 'POST':
        form = StationFeedbackForm(request.POST)
        if form.is_valid():
            form.save(assignment)
            return render(request, 'portal/station_feedback_done.html', {
                'student': student,
                'assignment': assignment,
            })
    else:
        form = StationFeedbackForm()

    return render(request, 'portal/station_feedback_form.html', {
        'student': student,
        'assignment': assignment,
        'form': form,
    })


@login_required
def beurteilung_view(request, assignment_id):
    """Read-only Ansicht der bestätigten Fremdbeurteilung für Auszubildende."""
    student = _get_student_or_403(request)

    from course.models import InternshipAssignment
    assignment = get_object_or_404(
        InternshipAssignment,
        pk=assignment_id,
        student=student,
    )

    from assessment.models import Assessment, STATUS_CONFIRMED
    assessment = get_object_or_404(Assessment, assignment=assignment, status=STATUS_CONFIRMED)

    ratings = (
        assessment.ratings
        .select_related('criterion')
        .order_by('criterion__order', 'criterion__name')
    )

    return render(request, 'portal/beurteilung_view.html', {
        'student': student,
        'assignment': assignment,
        'assessment': assessment,
        'ratings': ratings,
    })


# ── Wissensdatenbank (Portal) ────────────────────────────────────────────────

@login_required
def kb_list(request):
    """Delegiert die Wissensdatenbank-Liste an die Knowledge-App."""
    from knowledge.views import portal_kb_list
    return portal_kb_list(request)


@login_required
def kb_detail(request, public_id):
    """Delegiert die Wissensdatenbank-Detailansicht an die Knowledge-App."""
    from knowledge.views import portal_kb_detail
    return portal_kb_detail(request, public_id)


# ── Ankündigungen (Portal) ────────────────────────────────────────────────────

@login_required
def announcement_list(request):
    """Delegiert die Ankündigungsliste an die Announcements-App."""
    from announcements.views import portal_announcement_list
    return portal_announcement_list(request)


@login_required
def announcement_detail(request, public_id):
    """Delegiert die Ankündigungs-Detailansicht an die Announcements-App."""
    from announcements.views import portal_announcement_detail
    return portal_announcement_detail(request, public_id)


@login_required
def announcement_acknowledge(request, public_id):
    """Delegiert die Kenntnisnahme einer Ankündigung an die Announcements-App."""
    from announcements.views import portal_acknowledge
    return portal_acknowledge(request, public_id)


# ── Einsatzwünsche ───────────────────────────────────────────────────────

@login_required
def einsatzwuensche(request):
    """Nachwuchskraft gibt Wünsche für Praktikumseinsätze an."""
    student = _get_student_or_403(request)

    from student.models import InternshipPreference
    from portal.forms import InternshipPreferenceForm

    pref, _ = InternshipPreference.objects.get_or_create(student=student)

    if request.method == 'POST':
        form = InternshipPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ihre Einsatzwünsche wurden gespeichert.')
            return redirect('portal:einsatzwuensche')
    else:
        form = InternshipPreferenceForm(instance=pref)

    return render(request, 'portal/einsatzwuensche.html', {
        'student': student,
        'form': form,
    })


# ── Ausbildungsplan (Soll-Ist-Abgleich) ──────────────────────────────────

@login_required
def kompetenzmatrix(request):
    """Kompetenzmatrix der eigenen Nachwuchskraft im Portal."""
    student = _get_student_or_403(request)
    from services.competence_matrix import get_competence_matrix
    matrix = get_competence_matrix(student)
    return render(request, 'portal/kompetenzmatrix.html', {
        'student': student,
        'matrix':  matrix,
    })


@login_required
def ausbildungsplan(request):
    """Ausbildungsfortschritt der eigenen Nachwuchskraft."""
    student = _get_student_or_403(request)

    from course.curriculum import get_curriculum_status
    curriculum_status = get_curriculum_status(student)

    # Zusammenfassung
    mandatory = [r for r in curriculum_status if r['requirement'].is_mandatory]
    done = sum(1 for r in mandatory if r['status'] == 'completed')
    total = len(mandatory)
    pct = int(done / total * 100) if total else 100

    return render(request, 'portal/ausbildungsplan.html', {
        'student': student,
        'curriculum_status': curriculum_status,
        'progress': {'done': done, 'total': total, 'pct': pct},
    })


# ── Dokumente (Generierung) ──────────────────────────────────────────────

@login_required
def dokumente(request):
    """Dokumentengenerierung für Nachwuchskräfte."""
    student = _get_student_or_403(request)

    from student.models import StudentDocumentTemplate
    templates = StudentDocumentTemplate.objects.filter(is_active=True, available_in_portal=True)

    return render(request, 'portal/dokumente.html', {
        'student': student,
        'document_templates': templates,
    })


@login_required
def dokument_generieren(request, template_pk):
    """Dokument aus Vorlage generieren und in Akte ablegen."""
    student = _get_student_or_403(request)

    if request.method != 'POST':
        return redirect('portal:dokumente')

    from datetime import date as _date
    from student.models import StudentDocumentTemplate
    from services.paperless import PaperlessService
    from document.contexts import student_context, course_context, creator_context, meta_context
    from document.render import render_docx, upload_to_paperless

    template_obj = get_object_or_404(
        StudentDocumentTemplate, pk=template_pk, is_active=True, available_in_portal=True,
    )

    # Im Portal generiert die Nachwuchskraft das Dokument selbst → sie ist
    # zugleich „Ersteller". creator_context wird mit ihrem User-Account befüllt.
    context = {
        **student_context(student),
        **course_context(student.course),
        **creator_context(getattr(student, 'user', None)),
        **meta_context(),
    }

    try:
        file_bytes = render_docx(template_obj.template_file.path, context)
    except Exception as e:
        messages.error(request, f'Fehler beim Erstellen des Dokuments: {e}')
        return redirect('portal:dokumente')

    today_str = _date.today().strftime('%Y%m%d')
    title = f'{template_obj.name} – {student.first_name} {student.last_name} – {_date.today().strftime("%d.%m.%Y")}'
    filename = f'{template_obj.name}_{student.last_name}_{today_str}.docx'
    doc_id = upload_to_paperless(
        file_bytes=file_bytes,
        title=title,
        student_id=student.pk,
        filename=filename,
    )
    if doc_id:
        messages.success(request, f'„{template_obj.name}" wurde erstellt und in Ihrer Akte abgelegt.')

        # PDF von Paperless laden und per E-Mail an die NK senden
        try:
            from services.models import NotificationTemplate
            from services.email import send_mail as send_email

            email = student.email_private or (student.email_id or '')
            if email:
                pdf_bytes = PaperlessService.download_pdf(doc_id)
                if pdf_bytes:
                    anrede = f'Guten Tag {student.first_name} {student.last_name},'
                    subject, body = NotificationTemplate.render('document_generated', {
                        'anrede': anrede,
                        'student_vorname': student.first_name,
                        'student_nachname': student.last_name,
                        'dokument_name': template_obj.name,
                    })
                    pdf_filename = f'{template_obj.name}_{student.last_name}_{today_str}.pdf'
                    send_email(
                        subject=subject,
                        body_text=body,
                        recipient_list=[email],
                        attachments=[(pdf_filename, pdf_bytes, 'application/pdf')],
                    )
        except Exception:
            pass
    else:
        messages.error(request, 'Upload zu Paperless fehlgeschlagen.')
    return redirect('portal:dokumente')


# ── Nachrichten (Ticket-System) ──────────────────────────────────────────────

@login_required
def nachrichten(request):
    """Liste aller eigenen Anfragen + Formular für neue Anfrage."""
    student = _get_student_or_403(request)

    from student.models import StudentInquiry
    from portal.forms import StudentInquiryForm

    inquiries = StudentInquiry.objects.filter(student=student)

    # Zähle Anfragen mit neuen Staff-Antworten (nach letzter eigener Antwort)
    unread_count = 0
    for inq in inquiries:
        last_student_reply = inq.replies.filter(is_staff_reply=False).order_by('-created_at').first()
        cutoff = last_student_reply.created_at if last_student_reply else inq.created_at
        if inq.replies.filter(is_staff_reply=True, created_at__gt=cutoff).exists():
            unread_count += 1

    form = StudentInquiryForm()

    return render(request, 'portal/nachrichten.html', {
        'student': student,
        'inquiries': inquiries,
        'form': form,
        'unread_count': unread_count,
    })


@login_required
def nachricht_create(request):
    """Neue Anfrage erstellen."""
    student = _get_student_or_403(request)

    if request.method != 'POST':
        return redirect('portal:nachrichten')

    from portal.forms import StudentInquiryForm
    form = StudentInquiryForm(request.POST, request.FILES)
    if form.is_valid():
        inquiry = form.save(commit=False)
        inquiry.student = student
        inquiry.save()

        # Staff benachrichtigen
        try:
            from django.urls import reverse
            from services.models import notify_staff, NotificationTemplate
            from django.core.mail import send_mail
            from django.conf import settings

            detail_url = request.build_absolute_uri(
                reverse('student:student_detail', args=[student.pk])
            )
            notify_staff(
                message=f'Neue Anfrage von {student.first_name} {student.last_name}: „{inquiry.subject}"',
                link=reverse('student:student_detail', args=[student.pk]),
                icon='bi-chat-left-text',
                category='Anfrage',
            )

            # E-Mail via NotificationTemplate
            subject, body = NotificationTemplate.render('inquiry_new', {
                'student_vorname': student.first_name,
                'student_nachname': student.last_name,
                'betreff': inquiry.subject,
                'detail_url': detail_url,
            })
            from django.contrib.auth.models import User
            staff_emails = list(
                User.objects.filter(
                    groups__name__in=['ausbildungsleitung', 'ausbildungsreferat'],
                    is_active=True,
                ).exclude(email='').values_list('email', flat=True).distinct()
            )
            if staff_emails:
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, staff_emails, fail_silently=True)
        except Exception:
            pass

        messages.success(request, 'Ihre Anfrage wurde gesendet.')
    else:
        for err in form.errors.values():
            messages.error(request, ', '.join(err))

    return redirect('portal:nachrichten')


@login_required
def nachricht_detail(request, pk):
    """Konversationsansicht einer Anfrage + Antwort-Formular."""
    student = _get_student_or_403(request)

    from student.models import StudentInquiry, InquiryReply
    from portal.forms import InquiryReplyForm

    inquiry = get_object_or_404(StudentInquiry, pk=pk, student=student)

    if request.method == 'POST' and inquiry.status != 'closed':
        form = InquiryReplyForm(request.POST, request.FILES)
        if form.is_valid():
            InquiryReply.objects.create(
                inquiry=inquiry,
                author=request.user,
                message=form.cleaned_data['message'],
                attachment=form.cleaned_data.get('attachment') or '',
                is_staff_reply=False,
            )
            messages.success(request, 'Ihre Antwort wurde gesendet.')
            return redirect('portal:nachricht_detail', pk=pk)
    else:
        form = InquiryReplyForm()

    replies = inquiry.replies.select_related('author')

    return render(request, 'portal/nachricht_detail.html', {
        'student': student,
        'inquiry': inquiry,
        'replies': replies,
        'form': form,
    })


# ── Persönliche Daten bearbeiten ─────────────────────────────────────────────

@login_required
def daten_bearbeiten(request):
    """Telefonnummer und Adresse bearbeiten."""
    student = _get_student_or_403(request)

    from portal.forms import StudentPersonalDataForm
    from services.models import Adress

    if request.method == 'POST':
        form = StudentPersonalDataForm(request.POST)
        if form.is_valid():
            student.phone_number = form.cleaned_data['phone_number'] or None
            student.save(update_fields=['phone_number', 'updated_at'])

            street = form.cleaned_data['street']
            house_number = form.cleaned_data['house_number']
            zip_code = form.cleaned_data['zip_code']
            city = form.cleaned_data['city']

            if any([street, house_number, zip_code, city]):
                if student.address:
                    addr = student.address
                    addr.street = street
                    addr.house_number = house_number
                    addr.zip_code = zip_code
                    addr.city = city
                    addr.save()
                else:
                    addr = Adress.objects.create(
                        street=street,
                        house_number=house_number,
                        zip_code=zip_code,
                        city=city,
                    )
                    student.address = addr
                    student.save(update_fields=['address', 'updated_at'])
            elif student.address:
                # Alle Felder leer → Adresse entfernen
                old_addr = student.address
                student.address = None
                student.save(update_fields=['address', 'updated_at'])
                old_addr.delete()

            messages.success(request, 'Ihre Daten wurden aktualisiert.')
            return redirect('portal:daten')
    else:
        initial = {
            'phone_number': student.phone_number or '',
        }
        if student.address:
            initial.update({
                'street': student.address.street,
                'house_number': student.address.house_number,
                'zip_code': student.address.zip_code,
                'city': student.address.city,
            })
        form = StudentPersonalDataForm(initial=initial)

    return render(request, 'portal/daten_bearbeiten.html', {
        'student': student,
        'form': form,
    })
