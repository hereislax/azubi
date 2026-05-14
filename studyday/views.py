# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Views für das Ausbildungsreferat zur Verwaltung von Lern- und Studientagen.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    STATUS_APPROVED, STATUS_CANCELLED, STATUS_PENDING, STATUS_REJECTED,
    StudyDayBlackout, StudyDayPolicy, StudyDayRequest,
)

logger = logging.getLogger(__name__)


def _require_referat(request):
    """Prüft ob der Nutzer Ausbildungsreferat oder -leitung ist."""
    from services.roles import is_training_director, is_training_office
    if not (is_training_director(request.user) or is_training_office(request.user)):
        raise PermissionDenied


def _require_study_day_management(request):
    """Lerntage-Verwaltung: Leitung immer, Referat nur mit can_manage_absences."""
    from services.roles import is_training_director, is_training_office, get_training_office_profile
    if is_training_director(request.user):
        return
    if is_training_office(request.user):
        training_office_profile = get_training_office_profile(request.user)
        if training_office_profile and training_office_profile.can_manage_absences:
            return
    raise PermissionDenied


def _require_study_day_approval(request):
    """Lerntage-Genehmigung: Leitung immer, Referat nur mit can_approve_study_days."""
    from services.roles import is_training_director, is_training_office, get_training_office_profile
    if is_training_director(request.user):
        return
    if is_training_office(request.user):
        training_office_profile = get_training_office_profile(request.user)
        if training_office_profile and training_office_profile.can_approve_study_days:
            return
    raise PermissionDenied


# ── Antragsliste ──────────────────────────────────────────────────────────────

@login_required
def request_list(request):
    _require_study_day_management(request)

    qs = StudyDayRequest.objects.select_related(
        'student__course__job_profile', 'approved_by', 'cancelled_by'
    ).order_by('-date')

    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    student_filter = request.GET.get('student', '').strip()
    if student_filter:
        qs = qs.filter(
            student__first_name__icontains=student_filter
        ) | qs.filter(
            student__last_name__icontains=student_filter
        ) | qs.filter(
            student__student_id__icontains=student_filter
        )

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    pending_count = StudyDayRequest.objects.filter(status=STATUS_PENDING).count()

    return render(request, 'studyday/request_list.html', {
        'page_obj': page,
        'status_filter': status_filter,
        'student_filter': student_filter,
        'pending_count': pending_count,
        'status_choices': [
            ('', 'Alle'),
            (STATUS_PENDING,   'Ausstehend'),
            (STATUS_APPROVED,  'Genehmigt'),
            (STATUS_REJECTED,  'Abgelehnt'),
            (STATUS_CANCELLED, 'Storniert'),
        ],
    })


# ── Entscheidung (Freigabe / Ablehnung) ───────────────────────────────────────

@login_required
def request_decide(request, public_id):
    _require_study_day_approval(request)

    study_request = get_object_or_404(
        StudyDayRequest.objects.select_related('student__course__job_profile'),
        public_id=public_id,
    )

    if study_request.status != STATUS_PENDING:
        messages.warning(request, 'Dieser Antrag ist nicht mehr ausstehend und kann nicht entschieden werden.')
        return redirect('studyday:request_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            study_request.status = STATUS_APPROVED
            study_request.approved_by = request.user
            study_request.approved_at = timezone.now()
            study_request.save()

            _mirror_to_workflow(study_request, request.user,
                                'approve', comment='')

            from services.notifications import notify_student_of_study_day_decision
            notify_student_of_study_day_decision(request, study_request)

            messages.success(
                request,
                f'Lerntag am {study_request.date.strftime("%d.%m.%Y")} für '
                f'{study_request.student} wurde genehmigt.',
            )
            return redirect('studyday:request_list')

        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '').strip()
            study_request.status = STATUS_REJECTED
            study_request.approved_by = request.user
            study_request.approved_at = timezone.now()
            study_request.rejection_reason = rejection_reason
            study_request.save()

            _mirror_to_workflow(study_request, request.user,
                                'reject', comment=rejection_reason)

            from services.notifications import notify_student_of_study_day_decision
            notify_student_of_study_day_decision(request, study_request)

            messages.success(
                request,
                f'Lerntag am {study_request.date.strftime("%d.%m.%Y")} für '
                f'{study_request.student} wurde abgelehnt.',
            )
            return redirect('studyday:request_list')

    from .models import get_study_day_balance
    balance = get_study_day_balance(study_request.student)

    return render(request, 'studyday/request_decide.html', {
        'study_request': study_request,
        'balance': balance,
    })


# ── Stornierung (nur bereits genehmigte Tage) ─────────────────────────────────

@login_required
def request_cancel(request, public_id):
    _require_study_day_approval(request)

    study_request = get_object_or_404(
        StudyDayRequest.objects.select_related('student'),
        public_id=public_id,
    )

    if study_request.status != STATUS_APPROVED:
        messages.warning(request, 'Nur genehmigte Lerntage können storniert werden.')
        return redirect('studyday:request_list')

    if request.method == 'POST':
        study_request.status = STATUS_CANCELLED
        study_request.cancelled_by = request.user
        study_request.cancelled_at = timezone.now()
        study_request.save()
        study_request.bump_notification_sequence()

        from services.notifications import notify_student_of_study_day_cancellation
        notify_student_of_study_day_cancellation(request, study_request)

        messages.success(
            request,
            f'Lerntag am {study_request.date.strftime("%d.%m.%Y")} für '
            f'{study_request.student} wurde storniert.',
        )
        return redirect('studyday:request_list')

    return render(request, 'studyday/request_cancel_confirm.html', {
        'study_request': study_request,
    })


# ── Policy-Einstellungen ──────────────────────────────────────────────────────

@login_required
def policy_settings(request):
    from services.roles import is_training_director
    if not is_training_director(request.user):
        raise PermissionDenied

    from course.models import JobProfile
    from .models import SCOPE_CHOICES, ALLOCATION_CHOICES

    job_profiles = JobProfile.objects.order_by('job_profile')
    policy_map = {
        p.job_profile_id: p
        for p in StudyDayPolicy.objects.prefetch_related('blackouts').all()
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        jp_pk = request.POST.get('job_profile_id')
        jp = get_object_or_404(JobProfile, pk=jp_pk)

        # ── Regelung löschen ──────────────────────────────────────────────────
        if action == 'delete':
            StudyDayPolicy.objects.filter(job_profile=jp).delete()
            messages.success(request, f'Regelung für „{jp.job_profile}" gelöscht.')
            return redirect('studyday:policy_settings')

        # ── Sperrzeitraum löschen ─────────────────────────────────────────────
        if action == 'delete_blackout':
            blackout_pk = request.POST.get('blackout_id')
            StudyDayBlackout.objects.filter(pk=blackout_pk, policy__job_profile=jp).delete()
            messages.success(request, 'Sperrzeitraum gelöscht.')
            return redirect(f'{request.path}#jp-{jp_pk}')

        # ── Sperrzeitraum hinzufügen ──────────────────────────────────────────
        if action == 'add_blackout':
            policy = policy_map.get(jp.pk)
            if not policy:
                messages.error(request, 'Bitte zuerst eine Grundregelung speichern.')
                return redirect(f'{request.path}#jp-{jp_pk}')
            try:
                bo_start = _parse_date(request.POST.get('blackout_start', ''))
                bo_end   = _parse_date(request.POST.get('blackout_end', ''))
                assert bo_start <= bo_end
            except (ValueError, AssertionError):
                messages.error(request, 'Ungültiger Sperrzeitraum: Bitte gültige Daten eingeben (Beginn ≤ Ende).')
                return redirect(f'{request.path}#jp-{jp_pk}')
            StudyDayBlackout.objects.create(
                policy=policy,
                start_date=bo_start,
                end_date=bo_end,
                label=request.POST.get('blackout_label', '').strip(),
                is_recurring_annually=bool(request.POST.get('blackout_recurring')),
            )
            messages.success(request, 'Sperrzeitraum hinzugefügt.')
            return redirect(f'{request.path}#jp-{jp_pk}')

        # ── Grundregelung speichern ───────────────────────────────────────────
        scope           = request.POST.get('scope', '')
        allocation_type = request.POST.get('allocation_type', '')
        notes           = request.POST.get('notes', '').strip()

        valid_scopes = [c[0] for c in SCOPE_CHOICES]
        valid_alloc  = [c[0] for c in ALLOCATION_CHOICES]

        if scope not in valid_scopes or allocation_type not in valid_alloc:
            messages.error(request, 'Ungültige Eingabe.')
            return redirect('studyday:policy_settings')

        try:
            amount = int(request.POST.get('amount', ''))
            assert amount > 0
        except (ValueError, AssertionError):
            messages.error(request, 'Die Anzahl der Tage (Jahr 1) muss eine positive Zahl sein.')
            return redirect('studyday:policy_settings')

        def _optional_int(key, min_val=0):
            val = request.POST.get(key, '').strip()
            if not val:
                return None
            try:
                n = int(val)
                assert n >= min_val
                return n
            except (ValueError, AssertionError):
                return None

        # Erlaubte Wochentage als kommaseparierter String
        selected_days = [
            d for d in request.POST.getlist('allowed_weekdays')
            if d.isdigit() and 0 <= int(d) <= 6
        ]
        allowed_weekdays = ','.join(selected_days)

        policy, created = StudyDayPolicy.objects.update_or_create(
            job_profile=jp,
            defaults={
                'scope':               scope,
                'allocation_type':     allocation_type,
                'amount':              amount,
                'amount_year2':        _optional_int('amount_year2', 1),
                'amount_year3':        _optional_int('amount_year3', 1),
                'cap_per_month':       _optional_int('cap_per_month', 1),
                'allow_carryover':     bool(request.POST.get('allow_carryover')),
                'exam_prep_days':      _optional_int('exam_prep_days', 1),
                'min_advance_days':    int(request.POST.get('min_advance_days') or 0),
                'max_days_per_request': max(1, int(request.POST.get('max_days_per_request') or 1)),
                'allowed_weekdays':    allowed_weekdays,
                'notes':               notes,
            },
        )
        verb = 'angelegt' if created else 'aktualisiert'
        messages.success(request, f'Regelung für „{jp.job_profile}" {verb}.')
        return redirect(f'{request.path}#jp-{jp_pk}')

    profiles_with_policy = [
        (jp, policy_map.get(jp.pk))
        for jp in job_profiles
    ]

    return render(request, 'studyday/policy_settings.html', {
        'profiles_with_policy': profiles_with_policy,
        'scope_choices':        SCOPE_CHOICES,
        'allocation_choices':   ALLOCATION_CHOICES,
        'weekday_choices':      list(enumerate(['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'])),
    })


def _parse_date(s):
    from datetime import date as _date
    return _date.fromisoformat(s.strip())


def _mirror_to_workflow(study_request, actor, action, comment=''):
    """Spiegelt eine Entscheidung an die Workflow-Engine.

    Die Engine ist parallel zum klassischen Status-Feld aktiv und führt einen
    sauberen Audit-Trail. Fehler werden geloggt aber nicht propagiert — die
    klassische Logik bleibt damit als Fallback intakt.
    """
    try:
        from workflow.engine import perform_action, get_instance_for, start_workflow, WorkflowError
        instance = get_instance_for(study_request)
        if instance is None:
            # Legacy-Datensatz ohne Workflow-Instanz → nachträglich starten
            instance = start_workflow('study_day_request', target=study_request,
                                       initiator=study_request.student.user
                                       if hasattr(study_request.student, 'user') else None)
        if instance and instance.is_active:
            perform_action(instance, actor=actor, action=action, comment=comment)
    except WorkflowError as exc:
        logger.warning('Workflow-Mirror fehlgeschlagen (%s): %s', action, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unerwarteter Fehler beim Workflow-Mirror: %s', exc)
