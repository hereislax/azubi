# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Views für das Abwesenheitsmanagement (Ausbildungsreferat / Ausbildungsleitung).
"""
import logging
import uuid
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AbsenceSettingsForm, SickLeaveCloseForm, SickLeaveCreateForm,
    VacationRequestForm,
)
from .models import (
    STATUS_APPROVED, STATUS_CANCELLED, STATUS_PENDING, STATUS_PROCESSED, STATUS_REJECTED,
    STATUS_CHOICES, SICK_TYPE_CHOICES,
    AbsenceSettings, SickLeave, StudentAbsenceState, VacationBatch, VacationRequest,
    VacationConfirmationTemplate, TRAFFIC_LIGHT_ICON, update_traffic_light,
)

logger = logging.getLogger(__name__)


# ── Berechtigungsprüfungen ────────────────────────────────────────────────────

def _require_referat(request):
    """Prüft ob der Nutzer Ausbildungsleitung oder Ausbildungsreferat ist."""
    from services.roles import is_training_director, is_training_office
    if not (is_training_director(request.user) or is_training_office(request.user)):
        raise PermissionDenied


def _require_absence_management(request):
    """Abwesenheitsverwaltung: Leitung immer, Referat nur mit can_manage_absences."""
    from services.roles import is_training_director, is_training_office, get_training_office_profile
    if is_training_director(request.user):
        return
    if is_training_office(request.user):
        training_office_profile = get_training_office_profile(request.user)
        if training_office_profile and training_office_profile.can_manage_absences:
            return
    raise PermissionDenied


def _require_vacation_approval(request):
    """Urlaubsgenehmigung: Leitung immer, Referat nur mit can_approve_vacation."""
    from services.roles import is_training_director, is_training_office, get_training_office_profile
    if is_training_director(request.user):
        return
    if is_training_office(request.user):
        training_office_profile = get_training_office_profile(request.user)
        if training_office_profile and training_office_profile.can_approve_vacation:
            return
    raise PermissionDenied


def _require_leitung(request):
    """Prüft ob der Nutzer Ausbildungsleitung ist."""
    from services.roles import is_training_director
    if not is_training_director(request.user):
        raise PermissionDenied


def _can_view_absence(request):
    """True wenn der Nutzer Abwesenheiten sehen darf (Referat, Leitung oder Ausbildungsverantwortliche)."""
    from services.roles import is_training_director, is_training_office, is_training_responsible
    return (
        is_training_director(request.user)
        or is_training_office(request.user)
        or is_training_responsible(request.user)
    )


# ── Urlaubsanträge ────────────────────────────────────────────────────────────

@login_required
def vacation_list(request):
    _require_absence_management(request)

    qs = VacationRequest.objects.select_related(
        'student', 'approved_by', 'batch'
    ).order_by('-start_date', '-created_at')

    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    kind_filter = request.GET.get('kind', '')
    if kind_filter == 'cancellation':
        qs = qs.filter(is_cancellation=True)
    elif kind_filter == 'vacation':
        qs = qs.filter(is_cancellation=False)

    student_filter = request.GET.get('student', '').strip()
    if student_filter:
        qs = qs.filter(
            student__first_name__icontains=student_filter
        ) | qs.filter(
            student__last_name__icontains=student_filter
        )

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    pending_count = VacationRequest.objects.filter(status=STATUS_PENDING).count()

    return render(request, 'absence/vacation_list.html', {
        'page_obj': page,
        'status_filter': status_filter,
        'kind_filter': kind_filter,
        'student_filter': student_filter,
        'pending_count': pending_count,
        'status_choices': [('', 'Alle')] + list(STATUS_CHOICES),
    })


@login_required
def vacation_create(request):
    """Manueller Urlaubs- oder Stornierungsantrag durch das Ausbildungsreferat."""
    _require_referat(request)

    form = VacationRequestForm(request.POST or None)
    is_cancellation = request.GET.get('type') == 'cancellation'

    if request.method == 'POST' and form.is_valid():
        vr = form.save(commit=False)
        vr.is_cancellation = is_cancellation
        vr.submitted_via_portal = False
        vr.save()
        kind = 'Stornierungsantrag' if is_cancellation else 'Urlaubsantrag'
        messages.success(request, f'{kind} für {vr.student} wurde erfasst.')
        return redirect('absence:vacation_list')

    from student.models import Student
    students = Student.objects.order_by('last_name', 'first_name')

    return render(request, 'absence/vacation_create.html', {
        'form': form,
        'is_cancellation': is_cancellation,
        'students': students,
    })


@login_required
def vacation_detail(request, public_id):
    _require_referat(request)
    vr = get_object_or_404(
        VacationRequest.objects.select_related('student', 'approved_by', 'batch', 'original_request'),
        public_id=public_id,
    )
    cancellations = vr.cancellation_requests.all() if not vr.is_cancellation else []
    return render(request, 'absence/vacation_detail.html', {
        'vr': vr,
        'cancellations': cancellations,
    })


@login_required
def vacation_decide(request, public_id):
    """Genehmigung oder Ablehnung eines Urlaubsantrags durch das Ausbildungsreferat."""
    _require_vacation_approval(request)

    vr = get_object_or_404(
        VacationRequest.objects.select_related('student'),
        public_id=public_id,
    )

    if vr.status != STATUS_PENDING:
        messages.warning(request, 'Dieser Antrag ist nicht mehr ausstehend.')
        return redirect('absence:vacation_detail', public_id=public_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            vr.status = STATUS_APPROVED
            vr.approved_by = request.user
            vr.approved_at = timezone.now()
            vr.save()
            kind = 'Stornierungsantrag' if vr.is_cancellation else 'Urlaubsantrag'
            messages.success(request, f'{kind} für {vr.student} wurde genehmigt.')
            _notify_student_vacation_decision(vr, request)
            return redirect('absence:vacation_list')

        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            vr.status = STATUS_REJECTED
            vr.approved_by = request.user
            vr.approved_at = timezone.now()
            vr.rejection_reason = reason
            vr.save()
            kind = 'Stornierungsantrag' if vr.is_cancellation else 'Urlaubsantrag'
            messages.success(request, f'{kind} für {vr.student} wurde abgelehnt.')
            _notify_student_vacation_decision(vr, request)
            return redirect('absence:vacation_list')

    return render(request, 'absence/vacation_decide.html', {'vr': vr})


@login_required
def vacation_cancel_create(request, public_id):
    """
    Erstellt einen Stornierungsantrag für einen bereits genehmigten/bearbeiteten Urlaubsantrag.
    Verwendbar sowohl durch das Ausbildungsreferat als auch durch Nachwuchskräfte im Portal.
    """
    _require_referat(request)

    original = get_object_or_404(
        VacationRequest.objects.select_related('student'),
        public_id=public_id,
        is_cancellation=False,
    )

    if original.status not in (STATUS_APPROVED, STATUS_PROCESSED):
        messages.warning(request, 'Nur genehmigte oder bereits bearbeitete Anträge können storniert werden.')
        return redirect('absence:vacation_detail', public_id=public_id)

    # Prüfen ob bereits ein offener Stornierungsantrag existiert
    existing = original.cancellation_requests.filter(
        status__in=(STATUS_PENDING, STATUS_APPROVED)
    ).first()
    if existing:
        messages.warning(request, 'Es existiert bereits ein offener Stornierungsantrag.')
        return redirect('absence:vacation_detail', public_id=public_id)

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        cancel_req = VacationRequest.objects.create(
            student=original.student,
            start_date=original.start_date,
            end_date=original.end_date,
            is_cancellation=True,
            original_request=original,
            notes=notes,
            submitted_via_portal=False,
        )
        messages.success(
            request,
            f'Stornierungsantrag für {original.student} wurde erstellt und wartet auf Genehmigung.',
        )
        return redirect('absence:vacation_detail', public_id=cancel_req.public_id)

    return render(request, 'absence/vacation_cancel_create.html', {'original': original})


# ── Krankmeldungen ────────────────────────────────────────────────────────────

@login_required
def sick_leave_list(request):
    _require_absence_management(request)

    qs = SickLeave.objects.select_related('student', 'created_by', 'closed_by').order_by('-start_date')

    open_filter = request.GET.get('open', '')
    if open_filter == '1':
        qs = qs.filter(end_date__isnull=True)
    elif open_filter == '0':
        qs = qs.filter(end_date__isnull=False)

    student_filter = request.GET.get('student', '').strip()
    if student_filter:
        qs = qs.filter(
            student__first_name__icontains=student_filter
        ) | qs.filter(
            student__last_name__icontains=student_filter
        )

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    open_count = SickLeave.objects.filter(end_date__isnull=True).count()

    return render(request, 'absence/sick_leave_list.html', {
        'page_obj': page,
        'open_filter': open_filter,
        'student_filter': student_filter,
        'open_count': open_count,
    })


@login_required
def sick_leave_create(request):
    _require_referat(request)

    form = SickLeaveCreateForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        sl = form.save(commit=False)
        sl.created_by = request.user
        sl.save()
        update_traffic_light(sl.student, request)
        messages.success(request, f'Krankmeldung für {sl.student} ab {sl.start_date.strftime("%d.%m.%Y")} erfasst.')
        return redirect('absence:sick_leave_list')

    from student.models import Student
    students = Student.objects.order_by('last_name', 'first_name')

    return render(request, 'absence/sick_leave_create.html', {
        'form': form,
        'students': students,
    })


@login_required
def sick_leave_close(request, public_id):
    _require_referat(request)

    sl = get_object_or_404(SickLeave.objects.select_related('student'), public_id=public_id)

    if not sl.is_open:
        messages.warning(request, 'Diese Krankmeldung ist bereits geschlossen.')
        return redirect('absence:sick_leave_list')

    form = SickLeaveCloseForm(request.POST or None, sick_leave=sl)

    if request.method == 'POST' and form.is_valid():
        sl.end_date  = form.cleaned_data['end_date']
        sl.closed_by = request.user
        sl.closed_at = timezone.now()
        if form.cleaned_data.get('notes'):
            sl.notes = (sl.notes + '\n' + form.cleaned_data['notes']).strip()
        sl.save()
        update_traffic_light(sl.student, request)
        messages.success(
            request,
            f'Krankmeldung für {sl.student} bis {sl.end_date.strftime("%d.%m.%Y")} geschlossen.',
        )
        return redirect('absence:sick_leave_list')

    return render(request, 'absence/sick_leave_close.html', {'form': form, 'sl': sl})


# ── Urlaubsstelle-Portal ──────────────────────────────────────────────────────

def urlaubsstelle_portal(request, token):
    """
    Öffentliches Portal für die Urlaubsstelle (kein Login erforderlich).
    Zeigt alle genehmigten, noch nicht bearbeiteten Urlaubsanträge im Paket.
    """
    batch = get_object_or_404(VacationBatch, token=token)

    if batch.is_processed:
        return render(request, 'absence/urlaubsstelle_done.html', {
            'batch': batch,
            'already_processed': True,
        })

    requests_qs = batch.requests.select_related('student__course').order_by(
        'student__last_name', 'student__first_name', 'start_date'
    )

    if request.method == 'POST':
        errors = []
        updates = []

        for vr in requests_qs:
            curr_key = f'remaining_current_{vr.pk}'
            prev_key = f'remaining_previous_{vr.pk}'
            days_key = f'working_days_{vr.pk}'
            curr_raw = request.POST.get(curr_key, '').strip()
            prev_raw = request.POST.get(prev_key, '').strip()
            days_raw = request.POST.get(days_key, '').strip()

            if curr_raw == '' or prev_raw == '' or days_raw == '':
                errors.append(f'Bitte Arbeitstage und Resturlaub für {vr.student} ausfüllen.')
                continue

            try:
                curr = int(curr_raw)
                prev = int(prev_raw)
                days = int(days_raw)
            except ValueError:
                errors.append(f'Ungültige Eingabe für {vr.student}: nur ganze Zahlen erlaubt.')
                continue

            if curr < 0 or prev < 0 or days < 0:
                errors.append(f'Ungültige Eingabe für {vr.student}: negative Werte sind nicht erlaubt.')
                continue

            updates.append((vr, curr, prev, days))

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            for vr, curr, prev, days in updates:
                vr.remaining_days_current_year  = curr
                vr.remaining_days_previous_year = prev
                # Manuelle Arbeitstage nur speichern, wenn sie von der Berechnung abweichen –
                # ansonsten bleibt das Feld leer und das Property fällt zurück auf
                # ``duration_working_days``.
                vr.manual_working_days = days if days != vr.duration_working_days else None
                vr.status = STATUS_PROCESSED
                vr.save(update_fields=[
                    'remaining_days_current_year',
                    'remaining_days_previous_year',
                    'manual_working_days',
                    'status',
                    'updated_at',
                ])
                _notify_student_vacation_processed(vr, request)

            batch.processed_at = timezone.now()
            batch.processed_by_name = request.POST.get('processed_by_name', '').strip()
            # Token rotieren, damit der Link aus der Original-E-Mail nicht mehr aufgerufen
            # werden kann. Die Done-Seite wird mit dem neuen Token aufgerufen.
            batch.token = uuid.uuid4()
            batch.save(update_fields=['processed_at', 'processed_by_name', 'token'])

            return redirect('absence:urlaubsstelle_done', token=batch.token)

    return render(request, 'absence/urlaubsstelle_portal.html', {
        'batch': batch,
        'requests': requests_qs,
    })


def urlaubsstelle_done(request, token):
    batch = get_object_or_404(VacationBatch, token=token)
    requests_qs = batch.requests.select_related('student__course').order_by(
        'student__last_name', 'student__first_name', 'start_date'
    )

    # Word-Dokument generieren falls Template vorhanden
    if request.method == 'POST' and request.POST.get('action') == 'download':
        return _generate_vacation_word_document(batch, requests_qs, request.user)

    return render(request, 'absence/urlaubsstelle_done.html', {
        'batch': batch,
        'requests': requests_qs,
        'already_processed': False,
        'has_template': VacationConfirmationTemplate.objects.filter(is_active=True).exists(),
    })


def _generate_vacation_word_document(batch, requests_qs, user=None):
    """Generiert ein Word-Dokument mit allen Anträgen des Pakets."""
    template_obj = VacationConfirmationTemplate.objects.filter(is_active=True).first()
    if not template_obj:
        return HttpResponse('Keine aktive Vorlage gefunden.', status=404)

    try:
        from document.contexts import creator_context, meta_context
        from document.render import render_docx

        antraege = []
        for vr in requests_qs:
            antraege.append({
                'vorname':             vr.student.first_name,
                'nachname':            vr.student.last_name,
                'kurs':                str(vr.student.course) if vr.student.course else '–',
                'von':                 vr.start_date.strftime('%d.%m.%Y'),
                'bis':                 vr.end_date.strftime('%d.%m.%Y'),
                'arbeitstage':         vr.effective_working_days,
                'antragsart':          'Stornierung' if vr.is_cancellation else 'Urlaub',
                'resturlaub_aktuell':  vr.remaining_days_current_year if vr.remaining_days_current_year is not None else '–',
                'resturlaub_vorjahr':  vr.remaining_days_previous_year if vr.remaining_days_previous_year is not None else '–',
            })

        context = {
            **creator_context(user),
            **meta_context(),
            'antraege':       antraege,
            # 'bearbeitet_von' bleibt als domänenspezifischer Wert (eingegebener Name am Stapel)
            'bearbeitet_von': batch.processed_by_name or '–',
        }

        file_bytes = render_docx(template_obj.template_file.path, context)

        filename = f'Urlaubsantraege_{batch.sent_at.strftime("%Y%m%d")}.docx'
        response = HttpResponse(
            file_bytes,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as exc:
        logger.error('Word-Dokument-Generierung fehlgeschlagen: %s', exc)
        return HttpResponse(f'Fehler bei der Dokumentenerstellung: {exc}', status=500)


# ── Signiertes PDF ────────────────────────────────────────────────────────────

@login_required
def vacation_signed_pdf(request, public_id):
    """Erzeugt ein PDF der Urlaubsgenehmigung mit elektronischem Signaturblock."""
    _require_vacation_approval(request)

    vr = get_object_or_404(
        VacationRequest.objects.select_related('student', 'student__course', 'approved_by'),
        public_id=public_id,
    )

    if vr.status not in (STATUS_APPROVED, STATUS_PROCESSED):
        messages.warning(request, 'Nur genehmigte Anträge können als signiertes PDF heruntergeladen werden.')
        return redirect('absence:vacation_detail', public_id=public_id)

    if not vr.approved_by or not vr.approved_at:
        messages.error(request, 'Keine Genehmigungsdaten vorhanden.')
        return redirect('absence:vacation_detail', public_id=public_id)

    from services.signature import create_signed_pdf

    art = 'Stornierungsantrag' if vr.is_cancellation else 'Urlaubsantrag'
    title = f'Genehmigung – {art}'

    fields = [
        ('Nachwuchskraft',  f'{vr.student.first_name} {vr.student.last_name}'),
        ('Kurs',            str(vr.student.course) if vr.student.course else '–'),
        ('Art',             art),
        ('Zeitraum',        f'{vr.start_date.strftime("%d.%m.%Y")} – {vr.end_date.strftime("%d.%m.%Y")}'),
        ('Arbeitstage',     str(vr.duration_working_days)),
        ('Eingereicht am',  vr.created_at.strftime('%d.%m.%Y, %H:%M') + ' Uhr'),
    ]

    if vr.notes:
        fields.append(('Anmerkungen', vr.notes))

    signer_name = vr.approved_by.get_full_name() or vr.approved_by.username
    try:
        signer_role = vr.approved_by.userprofile.job_title or 'Ausbildungsreferat'
    except Exception:
        signer_role = 'Ausbildungsreferat'

    pdf_bytes = create_signed_pdf(
        title=title,
        fields=fields,
        signer_name=signer_name,
        signer_role=signer_role,
        signed_at=vr.approved_at,
    )

    safe_name = f'{vr.student.last_name}_{vr.student.first_name}'.replace(' ', '_')
    filename = f'Urlaubsgenehmigung_{safe_name}_{vr.start_date.strftime("%Y%m%d")}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── Einstellungen ─────────────────────────────────────────────────────────────

@login_required
def absence_settings(request):
    _require_leitung(request)

    settings_obj = AbsenceSettings.get()
    form = AbsenceSettingsForm(
        request.POST or None,
        initial={
            'vacation_office_email': settings_obj.vacation_office_email,
            'holiday_state':       settings_obj.holiday_state,
        },
    )

    # Vorlagen-Upload
    if request.method == 'POST':
        action = request.POST.get('action', 'save_settings')

        if action == 'save_settings' and form.is_valid():
            settings_obj.vacation_office_email = form.cleaned_data['vacation_office_email']
            settings_obj.holiday_state       = form.cleaned_data['holiday_state']
            settings_obj.save()
            messages.success(request, 'Einstellungen wurden gespeichert.')
            return redirect('absence:absence_settings')

        elif action == 'upload_template':
            name = request.POST.get('template_name', '').strip()
            tpl_file = request.FILES.get('template_file')
            if name and tpl_file:
                from services.validators import validate_docx
                from django.core.exceptions import ValidationError
                try:
                    validate_docx(tpl_file)
                except ValidationError as e:
                    messages.error(request, str(e.message))
                    return redirect('absence:absence_settings')
                VacationConfirmationTemplate.objects.create(
                    name=name,
                    template_file=tpl_file,
                    is_active=True,
                )
                messages.success(request, f'Vorlage „{name}" hochgeladen.')
            else:
                messages.error(request, 'Bitte Name und Datei angeben.')
            return redirect('absence:absence_settings')

        elif action == 'delete_template':
            tpl_pk = request.POST.get('template_pk')
            VacationConfirmationTemplate.objects.filter(pk=tpl_pk).delete()
            messages.success(request, 'Vorlage gelöscht.')
            return redirect('absence:absence_settings')

    templates = VacationConfirmationTemplate.objects.order_by('name')

    return render(request, 'absence/settings.html', {
        'form': form,
        'templates': templates,
        'settings_obj': settings_obj,
    })


# ── Benachrichtigungen ────────────────────────────────────────────────────────

def _notify_student_vacation_decision(vr: VacationRequest, request=None):
    """E-Mail an die Nachwuchskraft nach Genehmigung/Ablehnung."""
    student = vr.student
    if not student.email_id:
        return

    try:
        from services.email import send_mail
        from services.models import NotificationTemplate

        key = 'vacation_approved' if vr.status == STATUS_APPROVED else 'vacation_rejected'
        kind = 'Stornierungsantrag' if vr.is_cancellation else 'Urlaubsantrag'
        anrede = f'Guten Tag {student.first_name} {student.last_name},'

        portal_url = (
            request.build_absolute_uri('/portal/urlaub/')
            if request else '/portal/urlaub/'
        )

        subject, body = NotificationTemplate.render(key, {
            'anrede':           anrede,
            'student_vorname':  student.first_name,
            'student_nachname': student.last_name,
            'antragsart':       kind,
            'von':              vr.start_date.strftime('%d.%m.%Y'),
            'bis':              vr.end_date.strftime('%d.%m.%Y'),
            'arbeitstage':      str(vr.duration_working_days),
            'ablehnungsgrund':  vr.rejection_reason,
            'detail_url':       portal_url,
        })
        send_mail(subject=subject, body_text=body, recipient_list=[student.email_id])
    except Exception as exc:
        logger.warning('Urlaubsentscheidungs-Mail an %s fehlgeschlagen: %s', student, exc)

    # Portal-Benachrichtigung
    if student.user:
        try:
            from services.models import create_notification
            approved = vr.status == STATUS_APPROVED
            create_notification(
                student.user,
                message=(
                    f'{"Urlaubsantrag" if not vr.is_cancellation else "Stornierung"} '
                    f'{"genehmigt" if approved else "abgelehnt"}: '
                    f'{vr.start_date.strftime("%d.%m.%Y")}–{vr.end_date.strftime("%d.%m.%Y")}'
                ),
                link='/portal/urlaub/',
                icon='bi-check-circle' if approved else 'bi-x-circle',
                category='Urlaub',
            )
        except Exception:
            pass


def _notify_student_vacation_processed(vr: VacationRequest, request=None):
    """E-Mail an die Nachwuchskraft nach abschließender Bearbeitung durch die Urlaubsstelle."""
    student = vr.student
    if not student.email_id:
        return

    try:
        from services.email import send_mail
        from services.models import NotificationTemplate

        anrede = f'Guten Tag {student.first_name} {student.last_name},'
        portal_url = (
            request.build_absolute_uri('/portal/urlaub/')
            if request else '/portal/urlaub/'
        )

        subject, body = NotificationTemplate.render('vacation_processed', {
            'anrede':              anrede,
            'student_vorname':     student.first_name,
            'student_nachname':    student.last_name,
            'antragsart':          'Stornierung' if vr.is_cancellation else 'Urlaub',
            'von':                 vr.start_date.strftime('%d.%m.%Y'),
            'bis':                 vr.end_date.strftime('%d.%m.%Y'),
            'arbeitstage':         str(vr.effective_working_days),
            'resturlaub_aktuell':  str(vr.remaining_days_current_year) if vr.remaining_days_current_year is not None else '–',
            'resturlaub_vorjahr':  str(vr.remaining_days_previous_year) if vr.remaining_days_previous_year is not None else '–',
            'detail_url':          portal_url,
        })
        send_mail(subject=subject, body_text=body, recipient_list=[student.email_id])
    except Exception as exc:
        logger.warning('Urlaubsbearbeitung-Mail an %s fehlgeschlagen: %s', student, exc)

    if student.user:
        try:
            from services.models import create_notification
            create_notification(
                student.user,
                message=(
                    f'Urlaubsantrag bearbeitet: '
                    f'{vr.start_date.strftime("%d.%m.%Y")}–{vr.end_date.strftime("%d.%m.%Y")}'
                ),
                link='/portal/urlaub/',
                icon='bi-calendar-check',
                category='Urlaub',
            )
        except Exception:
            pass
