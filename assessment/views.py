# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Views für das Beurteilungssystem.

Öffentlich (kein Login):
  assessment_token_form  – Formular für Praxistutoren via Token (rotiert nach Submit)

Staff (Koordination / Leitung):
  assessment_list        – Übersicht aller Beurteilungen
  assessment_detail      – Einzelansicht + Bestätigungsaktion
  assessment_resend_token – Token-Mail erneut senden

Portal (Azubi):
  Liegt in portal/views.py, URL in portal/urls.py
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Assessment, STATUS_PENDING, STATUS_SUBMITTED, STATUS_CONFIRMED
from .forms import AssessmentTokenForm

logger = logging.getLogger(__name__)


# ── Hilfsfunktionen Berechtigungen ────────────────────────────────────────────

def _require_assessment_staff(request):
    """Prüft ob der Nutzer Leitung, Referat oder Koordination ist."""
    from services.roles import is_training_director, is_training_office, is_training_coordinator
    if not (
        is_training_director(request.user)
        or is_training_office(request.user)
        or is_training_coordinator(request.user)
    ):
        raise PermissionDenied


def _require_assessment_confirm(request):
    """Prüft ob der Nutzer Leitung oder Referat ist (für Beurteilungsbestätigung)."""
    from services.roles import is_training_director, is_training_office
    if not (is_training_director(request.user) or is_training_office(request.user)):
        raise PermissionDenied


def _coordinator_unit_pks(user):
    """
    Gibt das Set zugänglicher OE-PKs für eine Ausbildungskoordination zurück
    (alle eigenen + alle Kindeinheiten). Liefert None für Leitung/Referat
    (= unbeschränkter Zugriff).
    """
    from services.roles import is_training_director, is_training_office, is_training_coordinator, get_chief_instructor
    if is_training_director(user) or is_training_office(user) or user.is_staff:
        return None
    if is_training_coordinator(user):
        chief = get_chief_instructor(user)
        if not chief or not chief.coordination:
            return set()
        from instructor.views import _get_coordination_area
        descendant_pks, _, _ = _get_coordination_area(chief.coordination)
        return set(descendant_pks)
    return set()


def _require_assessment_access(request, assessment):
    """
    Prüft ob der aktuelle Nutzer auf das Assessment zugreifen darf.
    Für Koordination: Einsatz-OE muss im eigenen Bereich liegen.
    """
    allowed_pks = _coordinator_unit_pks(request.user)
    if allowed_pks is None:
        return  # Leitung/Referat → alles erlaubt
    if assessment.assignment.unit_id not in allowed_pks:
        raise PermissionDenied


def _require_assignment_access(request, assignment):
    """Wie _require_assessment_access, aber für ein Assignment direkt."""
    allowed_pks = _coordinator_unit_pks(request.user)
    if allowed_pks is None:
        return
    if assignment.unit_id not in allowed_pks:
        raise PermissionDenied


# ── Öffentliche Views (kein Login) ────────────────────────────────────────────

def assessment_token_form(request, token):
    """
    Beurteilungsformular für Praxistutoren.
    Kein Login erforderlich – Zugang ausschließlich via Token.

    Nach erfolgreichem Submit wird der Token rotiert (alter Link → 404).
    Das verhindert, dass jemand den weitergeleiteten Link erneut öffnet.
    """
    import uuid

    assessment = get_object_or_404(Assessment, token=token)

    if request.method == 'POST':
        form = AssessmentTokenForm(assessment, request.POST)
        if form.is_valid():
            form.save()
            _audit_token_submit(assessment, request)
            mirror_token_submit_to_workflow(assessment,
                                             actor_name=assessment.assessor_name)
            _notify_staff_assessment_submitted(assessment, request)
            assessment.token = uuid.uuid4()
            assessment.save(update_fields=['token'])
            return render(request, 'assessment/token_done.html', {
                'assessment': assessment,
            })
    else:
        form = AssessmentTokenForm(assessment)

    return render(request, 'assessment/token_form.html', {
        'assessment': assessment,
        'assignment': assessment.assignment,
        'template': assessment.template,
        'form': form,
    })


# ── Staff-Views ───────────────────────────────────────────────────────────────

@login_required
def assessment_list(request):
    """Übersicht aller Stationsbeurteilungen."""
    _require_assessment_staff(request)

    status_filter = request.GET.get('status', '')
    qs = (
        Assessment.objects
        .select_related('assignment__student', 'assignment__unit', 'assignment__schedule_block__course', 'template')
        .order_by('-assignment__end_date')
    )
    allowed_pks = _coordinator_unit_pks(request.user)
    if allowed_pks is not None:
        qs = qs.filter(assignment__unit_id__in=allowed_pks)
    if status_filter in (STATUS_PENDING, STATUS_SUBMITTED, STATUS_CONFIRMED):
        qs = qs.filter(status=status_filter)

    return render(request, 'assessment/list.html', {
        'assessments': qs,
        'status_filter': status_filter,
        'STATUS_PENDING': STATUS_PENDING,
        'STATUS_SUBMITTED': STATUS_SUBMITTED,
        'STATUS_CONFIRMED': STATUS_CONFIRMED,
    })


@login_required
def assessment_detail(request, public_id):
    """Detailansicht einer Stationsbeurteilung."""
    _require_assessment_staff(request)

    assessment = get_object_or_404(
        Assessment.objects.select_related(
            'assignment__student', 'assignment__unit',
            'assignment__schedule_block__course',
            'template', 'confirmed_by',
        ),
        public_id=public_id,
    )
    _require_assessment_access(request, assessment)
    ratings = assessment.ratings.select_related('criterion').order_by('criterion__order')

    # Selbstbeurteilung parallel anzeigen
    self_assessment = getattr(assessment.assignment, 'self_assessment', None)
    self_ratings = None
    if self_assessment:
        self_ratings = self_assessment.ratings.select_related('criterion').order_by('criterion__order')

    from services.roles import is_training_director, is_training_office, is_training_coordinator
    can_confirm = is_training_director(request.user) or is_training_office(request.user)

    # Kann der aktuell eingeloggte Nutzer die Info-Stufe abzeichnen?
    can_acknowledge = False
    try:
        from workflow.engine import get_instance_for
        from workflow.models import APPROVER_INFO
        instance = get_instance_for(assessment)
        if (instance and instance.is_active and instance.current_step
                and instance.current_step.approver_type == APPROVER_INFO
                and is_training_coordinator(request.user)):
            can_acknowledge = True
    except Exception:  # noqa: BLE001
        pass

    return render(request, 'assessment/detail.html', {
        'assessment': assessment,
        'ratings': ratings,
        'self_assessment': self_assessment,
        'self_ratings': self_ratings,
        'can_confirm': can_confirm,
        'can_acknowledge': can_acknowledge,
        'STATUS_SUBMITTED': STATUS_SUBMITTED,
        'STATUS_CONFIRMED': STATUS_CONFIRMED,
    })


@login_required
@require_POST
def assessment_acknowledge(request, public_id):
    """Kenntnisnahme durch die Ausbildungskoordination (Workflow-Info-Step)."""
    from services.roles import is_training_coordinator
    if not is_training_coordinator(request.user):
        raise PermissionDenied

    assessment = get_object_or_404(Assessment, public_id=public_id)
    _require_assessment_access(request, assessment)

    comment = request.POST.get('comment', '').strip()
    mirror_coord_ack_to_workflow(assessment, actor=request.user, comment=comment)
    messages.success(request, 'Kenntnisnahme vermerkt.')
    return redirect('assessment:detail', public_id=public_id)


@login_required
@require_POST
def assessment_confirm(request, public_id):
    """Bestätigt eine eingereichte Beurteilung."""
    _require_assessment_confirm(request)

    assessment = get_object_or_404(Assessment, public_id=public_id)
    if assessment.status != STATUS_SUBMITTED:
        messages.warning(request, 'Diese Beurteilung kann nicht bestätigt werden.')
        return redirect('assessment:detail', public_id=public_id)

    assessment.status = STATUS_CONFIRMED
    assessment.confirmed_by = request.user
    assessment.confirmed_at = timezone.now()
    assessment.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])
    mirror_office_confirm_to_workflow(assessment, actor=request.user)

    messages.success(request, 'Beurteilung erfolgreich bestätigt.')
    return redirect('assessment:detail', public_id=public_id)


@login_required
@require_POST
def assessment_send_for_assignment(request, assignment_pk):
    """
    Erstellt ein Assessment für einen Praktikumseinsatz (falls noch nicht vorhanden)
    und sendet den tokenbasierten Beurteilungslink an den Praxistutoren.
    Kann auch genutzt werden, um einen bestehenden Token erneut zu senden.
    Zugänglich direkt vom Bewertungsformular des Einsatzes.
    """
    _require_assessment_staff(request)

    from course.models import InternshipAssignment
    assignment = get_object_or_404(InternshipAssignment, pk=assignment_pk)
    _require_assignment_access(request, assignment)

    if not assignment.instructor or not assignment.instructor.email:
        messages.error(request, 'Kein Praxistutoren mit E-Mail-Adresse für diesen Einsatz hinterlegt.')
        return _redirect_to_assignment(request, assignment)

    # Berufsbild → aktive Vorlage suchen
    try:
        job_profile = assignment.student.course.job_profile
    except AttributeError:
        messages.error(request, 'Kein Berufsbild für diese Nachwuchskraft hinterlegt.')
        return _redirect_to_assignment(request, assignment)

    from .models import AssessmentTemplate
    template = AssessmentTemplate.objects.filter(job_profile=job_profile, active=True).first()
    if not template:
        messages.error(request, f'Keine aktive Beurteilungsvorlage für das Berufsbild „{job_profile}" vorhanden.')
        return _redirect_to_assignment(request, assignment)

    instructor = assignment.instructor
    assessment, created = Assessment.objects.get_or_create(
        assignment=assignment,
        defaults={
            'template': template,
            'assessor_name':  f'{instructor.first_name} {instructor.last_name}',
            'assessor_email': instructor.email,
            'status': STATUS_PENDING,
        },
    )

    if not created and assessment.status == 'confirmed':
        messages.warning(request, 'Diese Beurteilung wurde bereits bestätigt – kein erneuter Versand möglich.')
        return _redirect_to_assignment(request, assignment)

    if created:
        start_assessment_workflow(assessment, initiator=request.user)

    _send_assessment_token_mail(assessment, request)
    assessment.token_sent_at = timezone.now()
    assessment.save(update_fields=['token_sent_at'])

    action = 'erstellt und gesendet' if created else 'erneut gesendet'
    messages.success(request, f'Beurteilungslink {action} an {assessment.assessor_email}.')
    return _redirect_to_assignment(request, assignment)


def _redirect_to_assignment(request, assignment):
    """Leitet zurück zum Kalender des zugehörigen Blocks."""
    from django.urls import reverse
    from services.redirects import safe_next_url

    block = assignment.schedule_block
    course = block.course
    fallback = reverse('course:internship_calendar', kwargs={
        'course_pk': course.pk,
        'block_pk': block.pk,
    })
    return redirect(safe_next_url(request, fallback))


@login_required
@require_POST
def assessment_resend_token(request, public_id):
    """Sendet den Beurteilungslink erneut an den Praxistutoren."""
    _require_assessment_staff(request)

    assessment = get_object_or_404(Assessment, public_id=public_id)
    _require_assessment_access(request, assessment)
    if assessment.status != STATUS_PENDING:
        messages.warning(request, 'Beurteilungslink kann nur erneut gesendet werden, wenn noch keine Einreichung vorliegt.')
        return redirect('assessment:detail', public_id=public_id)

    if not assessment.assessor_email:
        messages.error(request, 'Keine E-Mail-Adresse für diesen Praxistutoren hinterlegt.')
        return redirect('assessment:detail', public_id=public_id)

    _send_assessment_token_mail(assessment, request)
    assessment.token_sent_at = timezone.now()
    assessment.save(update_fields=['token_sent_at'])
    messages.success(request, f'Beurteilungslink erneut gesendet an {assessment.assessor_email}.')
    return redirect('assessment:detail', public_id=public_id)


@login_required
@require_POST
def assessment_renew_token(request, public_id):
    """
    Erzeugt einen neuen Token für eine ausstehende Beurteilung und versendet
    den Link erneut. Setzt den Eskalations-Zähler zurück. Genutzt durch die
    Ausbildungskoordination, wenn ein bereits eskalierter Vorgang fortgesetzt
    werden soll.
    """
    import uuid

    _require_assessment_staff(request)

    assessment = get_object_or_404(Assessment, public_id=public_id)
    _require_assessment_access(request, assessment)
    if assessment.status != STATUS_PENDING:
        messages.warning(request, 'Token kann nur für ausstehende Beurteilungen erneuert werden.')
        return redirect('assessment:detail', public_id=public_id)

    if not assessment.assessor_email:
        messages.error(request, 'Keine E-Mail-Adresse für diesen Praxistutoren hinterlegt.')
        return redirect('assessment:detail', public_id=public_id)

    assessment.token = uuid.uuid4()
    assessment.token_sent_at = timezone.now()
    assessment.reminder_count = 0
    assessment.last_reminder_at = None
    assessment.escalated_at = None
    assessment.escalated_to = None
    assessment.save(update_fields=[
        'token', 'token_sent_at', 'reminder_count',
        'last_reminder_at', 'escalated_at', 'escalated_to',
    ])
    _send_assessment_token_mail(assessment, request)
    messages.success(
        request,
        f'Neuer Beurteilungslink an {assessment.assessor_email} gesendet. Eskalations-Zähler zurückgesetzt.',
    )
    return redirect('assessment:detail', public_id=public_id)


@login_required
@require_POST
def assessment_change_assessor(request, public_id):
    """
    Trägt einen anderen Praxistutoren für die Beurteilung ein und sendet den
    Link an die neue Adresse. Setzt den Eskalations-Zähler zurück.

    Erwartet POST: assessor_name, assessor_email
    """
    import uuid

    _require_assessment_staff(request)

    assessment = get_object_or_404(Assessment, public_id=public_id)
    _require_assessment_access(request, assessment)
    if assessment.status != STATUS_PENDING:
        messages.warning(request, 'Praxistutor kann nur für ausstehende Beurteilungen geändert werden.')
        return redirect('assessment:detail', public_id=public_id)

    new_name = (request.POST.get('assessor_name') or '').strip()
    new_email = (request.POST.get('assessor_email') or '').strip()
    if not new_name or not new_email:
        messages.error(request, 'Bitte Name und E-Mail-Adresse des neuen Praxistutors angeben.')
        return redirect('assessment:detail', public_id=public_id)

    assessment.assessor_name = new_name
    assessment.assessor_email = new_email
    assessment.token = uuid.uuid4()
    assessment.token_sent_at = timezone.now()
    assessment.reminder_count = 0
    assessment.last_reminder_at = None
    assessment.escalated_at = None
    assessment.escalated_to = None
    assessment.save(update_fields=[
        'assessor_name', 'assessor_email', 'token', 'token_sent_at',
        'reminder_count', 'last_reminder_at', 'escalated_at', 'escalated_to',
    ])
    _send_assessment_token_mail(assessment, request)
    messages.success(
        request,
        f'Praxistutor geändert auf {new_name} ({new_email}). Beurteilungslink versendet, Eskalation zurückgesetzt.',
    )
    return redirect('assessment:detail', public_id=public_id)


# ── Signiertes PDF ────────────────────────────────────────────────────────────

@login_required
def assessment_signed_pdf(request, public_id):
    """Erzeugt ein PDF der Beurteilungsbestätigung mit elektronischem Signaturblock."""
    _require_assessment_confirm(request)

    assessment = get_object_or_404(
        Assessment.objects.select_related(
            'assignment__student',
            'assignment__unit',
            'assignment__schedule_block',
            'confirmed_by',
        ),
        public_id=public_id,
    )

    if assessment.status != STATUS_CONFIRMED:
        messages.warning(request, 'Nur bestätigte Beurteilungen können als signiertes PDF heruntergeladen werden.')
        return redirect('assessment:detail', public_id=public_id)

    if not assessment.confirmed_by or not assessment.confirmed_at:
        messages.error(request, 'Keine Bestätigungsdaten vorhanden.')
        return redirect('assessment:detail', public_id=public_id)

    from django.http import HttpResponse
    from services.signature import create_signed_pdf

    assignment = assessment.assignment
    student = assignment.student

    fields = [
        ('Nachwuchskraft',      f'{student.first_name} {student.last_name}'),
        ('Organisationseinheit', str(assignment.unit)),
        ('Block',               assignment.schedule_block.name),
        ('Zeitraum',            f'{assignment.start_date.strftime("%d.%m.%Y")} – {assignment.end_date.strftime("%d.%m.%Y")}'),
        ('Praxistutor',         assessment.assessor_name or '–'),
    ]

    avg = assessment.average_grade
    if avg:
        fields.append(('Durchschnittsnote', f'Ø {avg}'))

    if assessment.overall_comment:
        fields.append(('Gesamtkommentar', assessment.overall_comment[:200]))

    if assessment.submitted_at:
        fields.append(('Eingereicht am', assessment.submitted_at.strftime('%d.%m.%Y, %H:%M') + ' Uhr'))

    signer_name = assessment.confirmed_by.get_full_name() or assessment.confirmed_by.username
    try:
        signer_role = assessment.confirmed_by.userprofile.job_title or 'Ausbildungskoordination'
    except Exception:
        signer_role = 'Ausbildungskoordination'

    pdf_bytes = create_signed_pdf(
        title='Beurteilungsbestätigung',
        fields=fields,
        signer_name=signer_name,
        signer_role=signer_role,
        signed_at=assessment.confirmed_at,
    )

    safe_name = f'{student.last_name}_{student.first_name}'.replace(' ', '_')
    filename = f'Beurteilung_{safe_name}_{assignment.start_date.strftime("%Y%m%d")}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── Anonyme Stationsbewertung – Auswertung ───────────────────────────────────

@login_required
def station_feedback_overview(request):
    """
    Auswertung der anonymen Stationsbewertungen nach Organisationseinheit.
    Filterbar nach Organisationseinheit und Praxisblock.
    """
    from django.db.models import Avg, Count
    from .models import StationFeedback, StationFeedbackCategory, StationFeedbackRating
    from organisation.models import OrganisationalUnit
    from course.models import ScheduleBlock

    _require_assessment_staff(request)

    # Filterparameter
    unit_pk     = request.GET.get('unit', '')
    block_pk    = request.GET.get('block', '')

    feedbacks = StationFeedback.objects.all()
    if unit_pk:
        feedbacks = feedbacks.filter(unit_id=unit_pk)
    if block_pk:
        feedbacks = feedbacks.filter(schedule_block_id=block_pk)

    # Kategorien (aktive)
    categories = StationFeedbackCategory.objects.filter(active=True).order_by('order', 'name')

    # Aggregation: pro Organisationseinheit + Kategorie → Durchschnitt + Anzahl
    rating_qs = (
        StationFeedbackRating.objects
        .filter(feedback__in=feedbacks)
        .values('feedback__unit', 'feedback__unit__name', 'feedback__unit__label', 'category', 'category__label')
        .annotate(avg_value=Avg('value'), count=Count('id'))
        .order_by('feedback__unit__name', 'category__order')
    )

    # Strukturieren: {unit_id: {category_id: {avg, count, label}}}
    unit_data = {}
    unit_labels = {}
    for row in rating_qs:
        uid  = row['feedback__unit']
        cid  = row['category']
        unit_labels[uid] = f"{row['feedback__unit__name']} – {row['feedback__unit__label']}"
        if uid not in unit_data:
            unit_data[uid] = {}
        unit_data[uid][cid] = {
            'avg':   round(row['avg_value'], 1) if row['avg_value'] else None,
            'count': row['count'],
            'label': row['category__label'],
        }

    # Gesamtanzahl Bewertungen pro Einheit
    submission_counts = (
        feedbacks
        .values('unit')
        .annotate(total=Count('id'))
    )
    unit_totals = {r['unit']: r['total'] for r in submission_counts}

    # Tabellenstruktur aufbauen: Liste von (unit_id, unit_label, total, [avg_per_cat])
    table_rows = []
    for uid, label in sorted(unit_labels.items(), key=lambda x: x[1]):
        cat_avgs = []
        for cat in categories:
            entry = unit_data.get(uid, {}).get(cat.pk)
            cat_avgs.append(entry['avg'] if entry else None)
        table_rows.append({
            'unit_id':   uid,
            'label':     label,
            'total':     unit_totals.get(uid, 0),
            'cat_avgs':  cat_avgs,
        })

    # Filter-Selectboxen befüllen
    all_units  = OrganisationalUnit.objects.filter(is_active=True).order_by('name')
    all_blocks = ScheduleBlock.objects.filter(block_type='internship').order_by('-start_date')

    # ── Trend-Analyse: Durchschnitt pro OE über ScheduleBlocks (chronologisch) ──
    trend_blocks = list(
        ScheduleBlock.objects
        .filter(block_type='internship', station_feedbacks__isnull=False)
        .distinct()
        .order_by('start_date')
    )

    trend_rows = []
    if trend_blocks:
        trend_qs = (
            StationFeedbackRating.objects
            .filter(feedback__schedule_block__in=trend_blocks)
            .values('feedback__unit', 'feedback__unit__name', 'feedback__unit__label',
                    'feedback__schedule_block')
            .annotate(avg_value=Avg('value'), count=Count('feedback', distinct=True))
            .order_by('feedback__unit__name', 'feedback__schedule_block__start_date')
        )

        # Strukturieren: {unit_id: {block_id: avg}}
        trend_data = {}
        trend_labels = {}
        for row in trend_qs:
            uid = row['feedback__unit']
            bid = row['feedback__schedule_block']
            trend_labels[uid] = f"{row['feedback__unit__name']} – {row['feedback__unit__label']}"
            trend_data.setdefault(uid, {})[bid] = round(row['avg_value'], 1)

        for uid, label in sorted(trend_labels.items(), key=lambda x: x[1]):
            block_avgs = trend_data.get(uid, {})
            values = []
            for b in trend_blocks:
                values.append(block_avgs.get(b.pk))

            # Trend: letzter vs. vorletzter vorhandener Wert
            filled = [(i, v) for i, v in enumerate(values) if v is not None]
            trend = None
            if len(filled) >= 2:
                prev_val = filled[-2][1]
                last_val = filled[-1][1]
                diff = round(last_val - prev_val, 1)
                if diff <= -0.3:
                    trend = 'better'   # niedrigere Note = besser (Schulnoten)
                elif diff >= 0.3:
                    trend = 'worse'
                else:
                    trend = 'stable'

            trend_rows.append({
                'unit_id': uid,
                'label': label,
                'values': values,
                'trend': trend,
            })

    return render(request, 'assessment/station_feedback_overview.html', {
        'table_rows':    table_rows,
        'categories':    categories,
        'all_units':     all_units,
        'all_blocks':    all_blocks,
        'unit_filter':   unit_pk,
        'block_filter':  block_pk,
        'total_count':   feedbacks.count(),
        'trend_blocks':  trend_blocks,
        'trend_rows':    trend_rows,
    })


# ── Interne Hilfsfunktionen ───────────────────────────────────────────────────

def _send_assessment_token_mail(assessment, request=None):
    """Sendet den tokenbasierten Beurteilungslink an den Praxistutoren."""
    from services.email import send_mail
    from services.models import NotificationTemplate

    token_url = (
        request.build_absolute_uri(f'/beurteilungen/praxistutor/{assessment.token}/')
        if request else f'/beurteilungen/praxistutor/{assessment.token}/'
    )
    assignment = assessment.assignment
    instructor = assignment.instructor

    context = {
        'anrede':           f'Guten Tag {instructor.first_name} {instructor.last_name},',
        'student_vorname':  assignment.student.first_name,
        'student_nachname': assignment.student.last_name,
        'einheit':          assignment.unit.name,
        'von':              assignment.start_date.strftime('%d.%m.%Y'),
        'bis':              assignment.end_date.strftime('%d.%m.%Y'),
        'block':            assignment.schedule_block.name,
        'beurteilungs_url': token_url,
    }
    subject, body = NotificationTemplate.render('assessment_token_sent', context)
    try:
        send_mail(subject=subject, body_text=body, recipient_list=[assessment.assessor_email])
        logger.info('Beurteilungslink gesendet → %s', assessment.assessor_email)
    except Exception as exc:
        logger.warning('Beurteilungslink-Mail fehlgeschlagen (%s): %s', assessment.assessor_email, exc)


def _audit_token_submit(assessment, request):
    """Loggt einen Tutor-Submit (anonymer Token-Zugriff) ins Audit-Log."""
    from auditlog.manual import log_event
    from auditlog.models import AuditLogEntry

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')

    log_event(
        action=AuditLogEntry.ACTION_SUBMIT,
        instance=assessment,
        user=None,
        changes={
            'assessor_name':  assessment.assessor_name,
            'assessor_email': assessment.assessor_email,
            'ip':             ip,
            'user_agent':     (request.META.get('HTTP_USER_AGENT') or '')[:200],
        },
        student_id=str(assessment.assignment.student_id),
    )


def _notify_staff_assessment_submitted(assessment, request=None):
    """Erstellt interne Benachrichtigung für Koordination/Leitung bei Einreichung."""
    from django.contrib.auth import get_user_model
    from services.models import create_notification

    User = get_user_model()
    detail_url = f'/beurteilungen/{assessment.public_id}/'
    msg = (
        f'Beurteilung eingereicht: {assessment.assignment.student} '
        f'– {assessment.assignment.unit}'
    )
    recipients = User.objects.filter(
        groups__name__in=['ausbildungsleitung', 'ausbildungsreferat', 'ausbildungskoordination'],
    ).distinct()
    for user in recipients:
        create_notification(
            user=user,
            message=msg,
            link=detail_url,
            icon='bi-clipboard-check',
            category='assessment',
        )


# ── Workflow-Integration ──────────────────────────────────────────────────────

def start_assessment_workflow(assessment, initiator=None):
    """Startet den ``assessment_confirm``-Workflow für eine neue Beurteilung."""
    try:
        from workflow.engine import start_workflow, get_instance_for, WorkflowError
        if get_instance_for(assessment) is not None:
            return None
        return start_workflow('assessment_confirm', target=assessment,
                               initiator=initiator)
    except WorkflowError as exc:
        logger.warning('Assessment-Workflow konnte nicht gestartet werden: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Assessment-Workflow-Start: %s', exc)
    return None


def mirror_token_submit_to_workflow(assessment, actor_name=''):
    """Spiegelt die Praxistutor-Einreichung (Stufe 1, ohne Login)."""
    try:
        from workflow.engine import (
            get_instance_for, perform_action, start_workflow, WorkflowError,
        )
        instance = get_instance_for(assessment)
        if instance is None:
            instance = start_workflow('assessment_confirm', target=assessment)
        if instance and instance.is_active and instance.current_step:
            perform_action(instance, actor=None,
                           actor_name=actor_name or assessment.assessor_name or 'Praxistutor',
                           action='approve',
                           comment='Beurteilung über Token-Link eingereicht.')
    except WorkflowError as exc:
        logger.warning('Assessment-Workflow-Mirror (Token-Submit) fehlgeschlagen: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Assessment-Workflow-Mirror (Submit): %s', exc)


def mirror_coord_ack_to_workflow(assessment, actor, comment=''):
    """Spiegelt die Kenntnisnahme durch die Koordination (Stufe 2, Info-Step)."""
    try:
        from workflow.engine import (
            get_instance_for, perform_action, WorkflowError,
        )
        instance = get_instance_for(assessment)
        if instance and instance.is_active and instance.current_step:
            perform_action(instance, actor=actor, action='acknowledge',
                           comment=comment or 'Zur Kenntnis genommen.')
    except WorkflowError as exc:
        logger.warning('Assessment-Workflow-Mirror (Coord-Ack) fehlgeschlagen: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Assessment-Workflow-Mirror (Ack): %s', exc)


def mirror_office_confirm_to_workflow(assessment, actor):
    """Spiegelt die Referat-Bestätigung (Stufe 3).

    Falls der Workflow noch in der Info-Stufe (Koordination) hängt, wird diese
    implizit als „zur Kenntnis genommen durch Bestätigung des Referats"
    abgezeichnet, bevor die Referat-Stufe genehmigt wird.
    """
    try:
        from workflow.engine import (
            get_instance_for, perform_action, start_workflow, WorkflowError,
        )
        from workflow.models import APPROVER_INFO
        instance = get_instance_for(assessment)
        if instance is None:
            initiator = assessment.confirmed_by or None
            instance = start_workflow('assessment_confirm', target=assessment,
                                       initiator=initiator)
            # Stufe 1 (Praxistutor) muss bereits abgeschlossen sein, sonst
            # können wir hier nicht ohne weiteres vor-springen.
            return

        # Falls noch in Info-Stufe: implizit acknowledge mit Referat-Bezug
        if (instance.current_step
                and instance.current_step.approver_type == APPROVER_INFO):
            perform_action(instance, actor=actor, action='acknowledge',
                           comment='Implizit durch Bestätigung des Ausbildungsreferats.')
            instance.refresh_from_db()

        if instance.is_active and instance.current_step:
            perform_action(instance, actor=actor, action='approve',
                           comment='Beurteilung bestätigt.')
    except WorkflowError as exc:
        logger.warning('Assessment-Workflow-Mirror (Office-Confirm) fehlgeschlagen: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Assessment-Workflow-Mirror (Confirm): %s', exc)
