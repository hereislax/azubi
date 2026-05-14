# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für die Ausbildungsnachweis-Verwaltung (Nachwuchskräfte- und Admin-Seite)."""
import io
import logging
from datetime import timedelta, date as date_cls

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RejectForm, TrainingDayFormSet, TrainingRecordCreateForm
from .models import TrainingRecord, TrainingDay, TrainingRecordExportTemplate

logger = logging.getLogger(__name__)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _get_student_or_403(request):
    """Gibt das Nachwuchskraft-Profil des eingeloggten Nutzers zurück oder wirft 403."""
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        raise PermissionDenied
    return student


def _can_review(user):
    """Prüft ob der Nutzer Ausbildungsnachweise prüfen darf (Leitung oder Ausbildungsverantwortliche)."""
    from services.roles import is_training_director, is_training_responsible
    return is_training_director(user) or is_training_responsible(user)


def _can_view_records(user):
    """Prüft ob der Nutzer Ausbildungsnachweise einsehen darf (Leitung, Referat oder Ausbildungsverantwortliche)."""
    from services.roles import is_training_director, is_training_office, is_training_responsible
    return is_training_director(user) or is_training_office(user) or is_training_responsible(user)


def _requires_proof(student):
    """Prüft ob das Berufsbild der Nachwuchskraft Ausbildungsnachweise erfordert."""
    try:
        return student.course.job_profile.requires_proof_of_training
    except AttributeError:
        return False


def _check_personalstelle_access(user, student):
    """Prüft ob ein Ausbildungsverantwortlicher Zugriff auf die Nachwuchskraft hat."""
    from services.roles import is_training_responsible
    if is_training_responsible(user) and not student.training_responsible_access_grants.filter(user=user).exists():
        raise PermissionDenied


# ─── Student-facing views ────────────────────────────────────────────────────

@login_required
def record_list(request):
    """Listenansicht der eigenen Ausbildungsnachweise."""
    student = _get_student_or_403(request)
    records = TrainingRecord.objects.filter(student=student).prefetch_related('days')
    return render(request, 'proofoftraining/record_list.html', {
        'student': student,
        'records': records,
        'requires_proof': _requires_proof(student),
    })


@login_required
def record_create(request):
    """Neuen Ausbildungsnachweis für eine Woche anlegen."""
    student = _get_student_or_403(request)
    if not _requires_proof(student):
        raise PermissionDenied

    today = date_cls.today()
    default_monday = today - timedelta(days=today.weekday())

    if request.method == 'POST':
        form = TrainingRecordCreateForm(request.POST)
        if form.is_valid():
            week_start = form.cleaned_data['week_start']
            if TrainingRecord.objects.filter(student=student, week_start=week_start).exists():
                form.add_error('week_start', 'Für diese Woche existiert bereits ein Ausbildungsnachweis.')
            else:
                record = form.save(commit=False)
                record.student = student
                record.save()
                for i in range(5):
                    TrainingDay.objects.create(record=record, date=week_start + timedelta(days=i))
                return redirect('proofoftraining:record_edit', public_id=record.public_id)
    else:
        form = TrainingRecordCreateForm(initial={'week_start': default_monday.isoformat()})

    return render(request, 'proofoftraining/record_create.html', {
        'form': form,
        'student': student,
    })


@login_required
def record_edit(request, public_id):
    """Ausbildungsnachweis bearbeiten (nur im Status Entwurf oder Abgelehnt)."""
    student = _get_student_or_403(request)
    record = get_object_or_404(TrainingRecord, public_id=public_id, student=student)

    if record.status not in ('draft', 'rejected'):
        return redirect('proofoftraining:record_view', public_id=public_id)

    if request.method == 'POST':
        formset = TrainingDayFormSet(request.POST, instance=record)
        if formset.is_valid():
            formset.save()
            if request.POST.get('action') == 'submit':
                record.status = 'submitted'
                record.submitted_at = timezone.now()
                record.rejection_reason = ''
                record.save()
                submit_record_to_workflow(record, initiator=request.user)
                messages.success(request, 'Ausbildungsnachweis eingereicht.')
                return redirect('proofoftraining:record_list')
            messages.success(request, 'Ausbildungsnachweis gespeichert.')
            return redirect('proofoftraining:record_edit', public_id=record.public_id)
    else:
        formset = TrainingDayFormSet(instance=record)

    return render(request, 'proofoftraining/record_edit.html', {
        'record': record,
        'formset': formset,
        'student': student,
    })


@login_required
def record_view(request, public_id):
    """Read-only-Ansicht eines eigenen Ausbildungsnachweises."""
    student = _get_student_or_403(request)
    record = get_object_or_404(TrainingRecord, public_id=public_id, student=student)
    return render(request, 'proofoftraining/record_view.html', {
        'record': record,
        'student': student,
    })


@login_required
@require_POST
def record_submit(request, public_id):
    """Ausbildungsnachweis zur Prüfung einreichen."""
    student = _get_student_or_403(request)
    record = get_object_or_404(TrainingRecord, public_id=public_id, student=student)
    if record.status not in ('draft', 'rejected'):
        messages.error(request, 'Dieser Nachweis kann nicht mehr eingereicht werden.')
        return redirect('proofoftraining:record_list')
    record.status = 'submitted'
    record.submitted_at = timezone.now()
    record.rejection_reason = ''
    record.save()
    submit_record_to_workflow(record, initiator=request.user)
    messages.success(request, 'Ausbildungsnachweis eingereicht.')
    try:
        from django.urls import reverse
        from services.models import notify_staff
        link = reverse('proofoftraining:admin_record_detail', kwargs={'student_pk': student.pk, 'public_id': record.public_id})
        notify_staff(
            message=f'Ausbildungsnachweis eingereicht: {student.first_name} {student.last_name} – KW {record.calendar_week}/{record.week_start.year}',
            link=link,
            icon='bi-journal-check',
            category='Ausbildungsnachweis',
        )
    except Exception:
        pass
    return redirect('proofoftraining:record_list')


# ─── Admin-facing views ───────────────────────────────────────────────────────

@login_required
def admin_record_detail(request, student_pk, public_id):
    """Admin-Detailansicht eines Ausbildungsnachweises mit Prüfungsmöglichkeit."""
    from student.models import Student
    if not _can_view_records(request.user):
        raise PermissionDenied
    student = get_object_or_404(Student, pk=student_pk)
    _check_personalstelle_access(request.user, student)
    record = get_object_or_404(TrainingRecord, public_id=public_id, student=student)
    reject_form = RejectForm() if _can_review(request.user) else None
    return render(request, 'proofoftraining/admin_record_detail.html', {
        'student': student,
        'record': record,
        'reject_form': reject_form,
        'can_review': _can_review(request.user),
    })


@login_required
@require_POST
def admin_record_approve(request, student_pk, public_id):
    """Eingereichten Ausbildungsnachweis annehmen."""
    from student.models import Student
    if not _can_review(request.user):
        raise PermissionDenied
    student = get_object_or_404(Student, pk=student_pk)
    record = get_object_or_404(TrainingRecord, public_id=public_id, student=student)
    if record.status != 'submitted':
        messages.error(request, 'Nur eingereichte Nachweise können angenommen werden.')
        return redirect('proofoftraining:admin_record_detail', student_pk=student_pk, public_id=public_id)
    record.status = 'approved'
    record.reviewed_by = request.user
    record.reviewed_at = timezone.now()
    record.rejection_reason = ''
    record.save()
    record.days.all().update(correction_note='')
    mirror_record_to_workflow(record, actor=request.user, action='approve')
    _notify_student(request, record, approved=True)
    messages.success(request, 'Ausbildungsnachweis angenommen.')
    return redirect('proofoftraining:admin_record_detail', student_pk=student_pk, public_id=public_id)


@login_required
@require_POST
def admin_record_reject(request, student_pk, public_id):
    """Eingereichten Ausbildungsnachweis mit Korrekturhinweis ablehnen."""
    from student.models import Student
    if not _can_review(request.user):
        raise PermissionDenied
    student = get_object_or_404(Student, pk=student_pk)
    record = get_object_or_404(TrainingRecord, public_id=public_id, student=student)
    if record.status != 'submitted':
        messages.error(request, 'Nur eingereichte Nachweise können abgelehnt werden.')
        return redirect('proofoftraining:admin_record_detail', student_pk=student_pk, public_id=public_id)
    form = RejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Bitte einen Korrekturhinweis angeben.')
        return redirect('proofoftraining:admin_record_detail', student_pk=student_pk, public_id=public_id)
    record.status = 'rejected'
    record.reviewed_by = request.user
    record.reviewed_at = timezone.now()
    record.rejection_reason = form.cleaned_data['rejection_reason']
    record.save()
    # Tagesbezogene Korrekturhinweise speichern
    for day in record.days.all():
        note = request.POST.get(f'day_correction_{day.pk}', '').strip()
        if day.correction_note != note:
            day.correction_note = note
            day.save(update_fields=['correction_note'])
    mirror_record_to_workflow(record, actor=request.user, action='reject',
                               comment=form.cleaned_data['rejection_reason'])
    _notify_student(request, record, approved=False)
    messages.success(request, 'Korrekturbedarf gemeldet.')
    return redirect('proofoftraining:admin_record_detail', student_pk=student_pk, public_id=public_id)


def _build_export_context(student, records, user=None):
    """Erstellt den Template-Kontext für den DOCX-Export der Ausbildungsnachweise."""
    from document.contexts import student_context, course_context, creator_context, meta_context
    nachweise = []
    for record in records:
        tage = []
        for d in record.days.all():
            tage.append({
                'datum':          d.date.strftime('%d.%m.%Y'),
                'wochentag':      d.weekday_name,
                'art':            d.get_day_type_display(),
                'beschreibung':   d.content,
                'korrekturhinweis': d.correction_note,
            })
        nachweise.append({
            'kw':     record.calendar_week,
            'jahr':   record.week_start.year,
            'von':    record.week_start.strftime('%d.%m.%Y'),
            'bis':    record.week_end.strftime('%d.%m.%Y'),
            'status': record.get_status_display(),
            'tage':   tage,
        })
    return {
        **student_context(student),
        **course_context(getattr(student, 'course', None)),
        **creator_context(user),
        **meta_context(),
        'nachweise':       nachweise,
    }


@login_required
def record_export(request):
    """Eigene Ausbildungsnachweise als Word-Dokument exportieren."""
    student = _get_student_or_403(request)
    template = TrainingRecordExportTemplate.objects.filter(is_active=True).first()
    if template is None:
        messages.error(request, 'Es ist keine Exportvorlage verfügbar. Bitte wenden Sie sich an die Ausbildungsleitung.')
        return redirect('proofoftraining:record_list')

    from document.render import render_docx
    records = TrainingRecord.objects.filter(student=student).prefetch_related('days').order_by('week_start')
    context = _build_export_context(student, records, user=request.user)
    file_bytes = render_docx(template.template_file.path, context)

    filename = f"Ausbildungsnachweise_{student.last_name}_{student.first_name}.docx"
    response = HttpResponse(file_bytes, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def admin_record_export(request, student_pk):
    """Admin-Export aller Ausbildungsnachweise einer Nachwuchskraft als Word-Dokument."""
    from student.models import Student
    if not _can_view_records(request.user):
        raise PermissionDenied
    student = get_object_or_404(Student, pk=student_pk)
    _check_personalstelle_access(request.user, student)

    template = TrainingRecordExportTemplate.objects.filter(is_active=True).first()
    if template is None:
        messages.error(request, 'Es ist keine Exportvorlage verfügbar.')
        return redirect('student:student_detail', pk=student_pk)

    from document.render import render_docx
    records = TrainingRecord.objects.filter(student=student).prefetch_related('days').order_by('week_start')
    context = _build_export_context(student, records, user=request.user)
    file_bytes = render_docx(template.template_file.path, context)

    filename = f"Ausbildungsnachweise_{student.last_name}_{student.first_name}.docx"
    response = HttpResponse(file_bytes, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _notify_student(request, record, approved: bool):
    """Benachrichtigt die Nachwuchskraft per E-Mail und In-App-Notification über den Prüfungsstatus."""
    from services.email import send_mail
    from services.models import NotificationTemplate

    student = record.student
    email = None
    if student.user and student.user.email:
        email = student.user.email
    elif student.email_private:
        email = student.email_private

    if not email:
        logger.warning('_notify_student: Keine E-Mail für Nachwuchskraft %s', student.pk)
        return

    key = 'proof_of_training_approved' if approved else 'proof_of_training_rejected'

    from services.notifications import is_email_enabled
    if not is_email_enabled(student.user, key):
        logger.info('Nachweis-Benachrichtigung übersprungen (deaktiviert): %s', email)
        return

    record_url = request.build_absolute_uri(f'/ausbildungsnachweise/{record.public_id}/')

    subject, body = NotificationTemplate.render(key, {
        'vorname':          student.first_name,
        'nachname':         student.last_name,
        'kw':               record.calendar_week,
        'jahr':             record.week_start.year,
        'von':              record.week_start.strftime('%d.%m.%Y'),
        'bis':              record.week_end.strftime('%d.%m.%Y'),
        'korrekturhinweis': record.rejection_reason,
        'detail_url':       record_url,
    })

    try:
        send_mail(subject=subject, body_text=body, recipient_list=[email])
        logger.info('Nachweis-Benachrichtigung an %s gesendet (record pk=%s)', email, record.pk)
    except Exception as exc:
        logger.warning('Nachweis-Benachrichtigung an %s fehlgeschlagen: %s', email, exc)
        messages.warning(
            request,
            f'Status gespeichert, aber Benachrichtigung an {student.first_name} {student.last_name} '
            f'konnte nicht gesendet werden: {exc}',
        )

    if student.user:
        try:
            from services.models import create_notification
            if approved:
                create_notification(
                    student.user,
                    message=f'Ausbildungsnachweis angenommen: KW {record.calendar_week}/{record.week_start.year}',
                    link=f'/ausbildungsnachweise/{record.public_id}/',
                    icon='bi-journal-check',
                    category='Ausbildungsnachweis',
                )
            else:
                create_notification(
                    student.user,
                    message=f'Ausbildungsnachweis: Korrekturbedarf KW {record.calendar_week}/{record.week_start.year}',
                    link=f'/ausbildungsnachweise/{record.public_id}/',
                    icon='bi-journal-x',
                    category='Ausbildungsnachweis',
                )
        except Exception:
            pass


# ── Workflow-Integration ──────────────────────────────────────────────────────

def submit_record_to_workflow(record, initiator):
    """Startet oder reicht den ``training_record``-Workflow für einen Nachweis ein.

    Beim ersten Submit wird eine neue Instanz angelegt. Bei einem Resubmit nach
    Ablehnung (``to_initiator`` → ``current_step is None``) wird die bestehende
    Instanz fortgeführt und die Revision hochgezählt.
    """
    try:
        from workflow.engine import (
            start_workflow, perform_action, get_instance_for, WorkflowError,
        )
        from workflow.models import ACTION_RESUBMIT
        instance = get_instance_for(record)
        if instance is None:
            return start_workflow('training_record', target=record,
                                   initiator=initiator)
        # Instanz existiert — Resubmit nur wenn beim Antragsteller (current_step=None)
        if instance.is_active and instance.current_step is None:
            perform_action(instance, actor=initiator, action=ACTION_RESUBMIT,
                           comment='Überarbeiteter Nachweis eingereicht.')
        return instance
    except WorkflowError as exc:
        logger.warning('Training-Record-Workflow konnte nicht (re-)gestartet werden: %s', exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Training-Record-Workflow-Start: %s', exc)
    return None


def mirror_record_to_workflow(record, actor, action, comment=''):
    """Spiegelt Approve/Reject-Aktionen an die Workflow-Engine."""
    try:
        from workflow.engine import (
            perform_action, get_instance_for, start_workflow, WorkflowError,
        )
        instance = get_instance_for(record)
        if instance is None:
            # Legacy-Datensatz ohne Workflow-Instanz — nachträglich starten
            initiator = record.student.user if hasattr(record.student, 'user') else None
            instance = start_workflow('training_record', target=record,
                                       initiator=initiator)
        if instance and instance.is_active and instance.current_step is not None:
            perform_action(instance, actor=actor, action=action, comment=comment)
    except WorkflowError as exc:
        logger.warning('Training-Record-Workflow-Mirror fehlgeschlagen (%s): %s',
                       action, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Training-Record-Workflow-Mirror: %s', exc)
