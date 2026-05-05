# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für Pflichtschulungen.

Berechtigungen:
- **Schreiben** (Anlegen, Bearbeiten, Löschen, Erfassen, Bulk):
    nur Ausbildungsleitung + Ausbildungsreferat (+ Staff)
- **Lesen** (Übersicht, Detail, Heatmap):
    zusätzlich Ausbildungsverantwortliche — beschränkt auf ihnen freigegebene NK
- **Portal**: Azubi sieht nur eigene Schulungen
- **Ausbildungskoordinationen**: kein Zugriff (auch nicht lesend)
"""
from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BulkCompletionForm, TrainingCompletionForm, TrainingTypeForm
from .models import TrainingCompletion, TrainingType
from .services import (
    STATUS_BADGE, STATUS_LABELS, STATUS_COMPLETED, STATUS_EXPIRED,
    STATUS_NEVER, STATUS_SOON_EXPIRING,
    applicable_training_types, compliance_status_for_student, derive_status,
    latest_completions,
)


# ── Berechtigungs-Helper ────────────────────────────────────────────────────

def _can_write(user) -> bool:
    from services.roles import is_training_director, is_training_office
    return user.is_authenticated and (
        user.is_staff or is_training_director(user) or is_training_office(user)
    )


def _can_read(user) -> bool:
    from services.roles import is_training_responsible
    return _can_write(user) or (user.is_authenticated and is_training_responsible(user))


def _require_write(request):
    if not _can_write(request.user):
        raise PermissionDenied


def _require_read(request):
    if not _can_read(request.user):
        raise PermissionDenied


def _accessible_students_for(user):
    """QuerySet aller NK, auf die ``user`` Lesezugriff hat."""
    from student.models import Student, TrainingResponsibleAccess
    if _can_write(user):
        return Student.objects.filter(anonymized_at__isnull=True)
    # Ausbildungsverantwortliche: nur freigegebene NK
    student_pks = TrainingResponsibleAccess.objects.filter(user=user).values_list('student_id', flat=True)
    return Student.objects.filter(pk__in=student_pks, anonymized_at__isnull=True)


def _student_or_403(user, student_pk):
    qs = _accessible_students_for(user)
    return get_object_or_404(qs, pk=student_pk)


# ── Schulungs-Typ CRUD ──────────────────────────────────────────────────────

@login_required
def training_type_list(request):
    """Übersicht aller Schulungstypen."""
    _require_read(request)
    from django.db.models import Count
    types = (
        TrainingType.objects
        .annotate(completion_count=Count('completions'))
        .order_by('-active', 'name')
    )
    return render(request, 'mandatorytraining/type_list.html', {
        'types':     types,
        'can_write': _can_write(request.user),
    })


@login_required
def training_type_create(request):
    _require_write(request)
    if request.method == 'POST':
        form = TrainingTypeForm(request.POST)
        if form.is_valid():
            tt = form.save()
            messages.success(request, f'Schulungs-Typ „{tt.name}" wurde angelegt.')
            return redirect('mandatorytraining:type_list')
    else:
        form = TrainingTypeForm()
    return render(request, 'mandatorytraining/type_form.html', {'form': form, 'action': 'Anlegen'})


@login_required
def training_type_edit(request, public_id):
    _require_write(request)
    tt = get_object_or_404(TrainingType, public_id=public_id)
    if request.method == 'POST':
        form = TrainingTypeForm(request.POST, instance=tt)
        if form.is_valid():
            form.save()
            messages.success(request, f'„{tt.name}" wurde aktualisiert.')
            return redirect('mandatorytraining:type_list')
    else:
        form = TrainingTypeForm(instance=tt)
    return render(request, 'mandatorytraining/type_form.html', {
        'form': form, 'action': 'Bearbeiten', 'training_type': tt,
    })


@login_required
def training_type_delete(request, public_id):
    _require_write(request)
    tt = get_object_or_404(TrainingType, public_id=public_id)
    if request.method == 'POST':
        try:
            name = tt.name
            tt.delete()
            messages.success(request, f'„{name}" wurde gelöscht.')
        except Exception as exc:
            messages.error(request, f'„{tt.name}" konnte nicht gelöscht werden (vorhandene Teilnahmen?): {exc}')
        return redirect('mandatorytraining:type_list')
    return render(request, 'mandatorytraining/type_confirm_delete.html', {'training_type': tt})


# ── Compliance-Übersicht (Heatmap) ──────────────────────────────────────────

@login_required
def overview(request):
    """Heatmap aller (sichtbaren) NK × aktive Schulungs-Typen."""
    _require_read(request)
    types = list(TrainingType.objects.filter(active=True).order_by('name'))
    students = (
        _accessible_students_for(request.user)
        .select_related('course__job_profile')
        .order_by('last_name', 'first_name')
    )
    rows = []
    for s in students:
        latest = latest_completions(s)
        cells = []
        for tt in types:
            if not tt.applies_to(s):
                cells.append({'na': True})
                continue
            c = latest.get(tt.pk)
            st = derive_status(c, tt)
            cells.append({
                'na':      False,
                'status':  st,
                'badge':   STATUS_BADGE[st],
                'label':   STATUS_LABELS[st],
                'date':    c.expires_on if c else None,
                'completion_pk': c.pk if c else None,
            })
        rows.append({'student': s, 'cells': cells})
    return render(request, 'mandatorytraining/overview.html', {
        'types':     types,
        'rows':      rows,
        'can_write': _can_write(request.user),
    })


# ── Pro-Azubi-Detail (im student_detail-Tab oder als eigene Seite) ─────────

@login_required
def student_detail(request, student_pk):
    """Pflichtschulungs-Detailseite einer NK (alle Teilnahmen + Status)."""
    _require_read(request)
    student = _student_or_403(request.user, student_pk)
    status = compliance_status_for_student(student)
    history = (
        TrainingCompletion.objects
        .filter(student=student)
        .select_related('training_type', 'registered_by')
        .order_by('training_type__name', '-completed_on')
    )
    return render(request, 'mandatorytraining/student_detail.html', {
        'student':   student,
        'status':    status,
        'history':   history,
        'can_write': _can_write(request.user),
    })


# ── Erfassung Einzel-Teilnahme ──────────────────────────────────────────────

@login_required
def completion_create(request, student_pk):
    _require_write(request)
    from student.models import Student
    student = get_object_or_404(Student.objects.filter(anonymized_at__isnull=True), pk=student_pk)
    type_pk = request.GET.get('type')
    initial = {}
    if type_pk:
        try:
            initial['training_type'] = int(type_pk)
        except ValueError:
            pass
    initial.setdefault('completed_on', date.today().isoformat())

    if request.method == 'POST':
        form = TrainingCompletionForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.student = student
            c.registered_by = request.user
            c.save()
            _maybe_attach_certificate(request, c)
            messages.success(request, f'Teilnahme erfasst: {c.training_type.name} am {c.completed_on:%d.%m.%Y}.')
            return redirect('mandatorytraining:student_detail', student_pk=student.pk)
    else:
        form = TrainingCompletionForm(initial=initial)
    return render(request, 'mandatorytraining/completion_form.html', {
        'student': student, 'form': form, 'action': 'Erfassen',
    })


@login_required
def completion_edit(request, public_id):
    _require_write(request)
    c = get_object_or_404(TrainingCompletion.objects.select_related('student', 'training_type'), public_id=public_id)
    if request.method == 'POST':
        form = TrainingCompletionForm(request.POST, instance=c)
        if form.is_valid():
            form.save()
            _maybe_attach_certificate(request, c)
            messages.success(request, 'Teilnahme aktualisiert.')
            return redirect('mandatorytraining:student_detail', student_pk=c.student_id)
    else:
        form = TrainingCompletionForm(instance=c)
    return render(request, 'mandatorytraining/completion_form.html', {
        'student': c.student, 'form': form, 'action': 'Bearbeiten', 'completion': c,
    })


@login_required
def completion_delete(request, public_id):
    _require_write(request)
    c = get_object_or_404(TrainingCompletion, public_id=public_id)
    student_pk = c.student_id
    if request.method == 'POST':
        c.delete()
        messages.success(request, 'Teilnahme entfernt.')
        return redirect('mandatorytraining:student_detail', student_pk=student_pk)
    return render(request, 'mandatorytraining/completion_confirm_delete.html', {'completion': c})


def _maybe_attach_certificate(request, completion: TrainingCompletion):
    """Lädt optional ein hochgeladenes Zertifikat in Paperless und verknüpft es."""
    f = request.FILES.get('certificate')
    if not f:
        return
    try:
        from services.paperless import upload_to_paperless_blob
    except ImportError:
        try:
            from document.render import upload_to_paperless
        except Exception:
            return
        else:
            try:
                title = f'Schulungszertifikat – {completion.student} – {completion.training_type.name} – {completion.completed_on:%d.%m.%Y}'
                doc_id = upload_to_paperless(
                    file_bytes=f.read(),
                    title=title,
                    student_id=completion.student.pk,
                    filename=f.name,
                    document_type='Schulungszertifikat',
                )
                if doc_id:
                    completion.certificate_paperless_id = doc_id
                    completion.save(update_fields=['certificate_paperless_id'])
            except Exception as exc:
                messages.warning(request, f'Zertifikat konnte nicht in Paperless hochgeladen werden: {exc}')


# ── Bulk-Erfassung ──────────────────────────────────────────────────────────

@login_required
def bulk_create(request):
    """Mehrere NK auf einmal als „abgeschlossen" markieren (nach gemeinsamer Schulung)."""
    _require_write(request)
    from student.models import Student
    if request.method == 'POST':
        form = BulkCompletionForm(request.POST)
        if form.is_valid():
            ids = form.cleaned_data['students']
            students = list(Student.objects.filter(pk__in=ids, anonymized_at__isnull=True))
            tt = form.cleaned_data['training_type']
            completed_on = form.cleaned_data['completed_on']
            expires_override = form.cleaned_data.get('expires_on_override')
            notes = form.cleaned_data.get('notes', '')

            created = 0
            for s in students:
                c = TrainingCompletion(
                    student=s,
                    training_type=tt,
                    completed_on=completed_on,
                    notes=notes,
                    registered_by=request.user,
                )
                if expires_override:
                    c.expires_on = expires_override
                c.save()
                created += 1
            messages.success(request, f'{created} Teilnahme(n) erfasst für „{tt.name}".')
            return redirect('mandatorytraining:overview')
    else:
        form = BulkCompletionForm()

    students = (
        Student.objects.filter(anonymized_at__isnull=True)
        .select_related('course__job_profile')
        .order_by('last_name', 'first_name')
    )
    return render(request, 'mandatorytraining/bulk_form.html', {
        'form': form, 'students': students,
    })


# ── Portal (Azubi sieht eigene Schulungen) ──────────────────────────────────

@login_required
def portal_my_trainings(request):
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        raise PermissionDenied
    status = compliance_status_for_student(student)
    history = (
        TrainingCompletion.objects
        .filter(student=student)
        .select_related('training_type')
        .order_by('-completed_on')
    )
    return render(request, 'mandatorytraining/portal.html', {
        'student': student,
        'status':  status,
        'history': history,
    })
