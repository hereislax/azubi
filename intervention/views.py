# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für das Maßnahmen-Modul.

Enthält Ansichten für Ausbildungsleitung und -referat (Listenansicht,
Erstellen, Detailansicht, Löschen) sowie die Kategorien-Verwaltung.
"""

import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Intervention, InterventionCategory,
    STATUS_CHOICES, STATUS_CLOSED, STATUS_ESCALATED, STATUS_IN_PROGRESS, STATUS_OPEN,
    TRIGGER_CHOICES, TRIGGER_ABSENCE, TRIGGER_ASSESSMENT,
)

logger = logging.getLogger(__name__)


def _require_referat(request):
    """Prüft ob der Nutzer Maßnahmen verwalten darf (Leitung oder Referat mit Berechtigung)."""
    from services.roles import is_training_director, is_training_office, get_training_office_profile
    if is_training_director(request.user):
        return
    if is_training_office(request.user):
        training_office_profile = get_training_office_profile(request.user)
        if training_office_profile and training_office_profile.can_manage_interventions:
            return
    raise PermissionDenied


# ── Liste ─────────────────────────────────────────────────────────────────────

@login_required
def intervention_list(request):
    _require_referat(request)

    qs = Intervention.objects.select_related(
        'student', 'category', 'created_by'
    ).order_by('-date')

    status_filter  = request.GET.get('status', '')
    student_filter = request.GET.get('student', '').strip()
    trigger_filter = request.GET.get('trigger', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if trigger_filter:
        qs = qs.filter(trigger_type=trigger_filter)
    if student_filter:
        qs = qs.filter(
            student__first_name__icontains=student_filter
        ) | qs.filter(
            student__last_name__icontains=student_filter
        )

    paginator = Paginator(qs, 30)
    page      = paginator.get_page(request.GET.get('page'))

    open_count = Intervention.objects.filter(
        status__in=[STATUS_OPEN, STATUS_IN_PROGRESS]
    ).count()

    return render(request, 'intervention/intervention_list.html', {
        'page_obj':       page,
        'status_filter':  status_filter,
        'student_filter': student_filter,
        'trigger_filter': trigger_filter,
        'open_count':     open_count,
        'status_choices': [('', 'Alle')] + STATUS_CHOICES,
        'trigger_choices': [('', 'Alle Auslöser')] + TRIGGER_CHOICES,
        'today':          date.today(),
    })


# ── Erstellen ─────────────────────────────────────────────────────────────────

@login_required
def intervention_create(request):
    _require_referat(request)

    from student.models import Student
    from absence.models import SickLeave
    from assessment.models import Assessment

    # Nachwuchskraft vorbelegen (aus Query-Parameter oder POST)
    student_pk = request.POST.get('student') or request.GET.get('student')
    student    = get_object_or_404(Student, pk=student_pk) if student_pk else None

    categories = InterventionCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        # Pflichtfelder aus dem POST-Body einlesen
        cat_pk       = request.POST.get('category')
        trigger_type = request.POST.get('trigger_type', '').strip()
        date_raw     = request.POST.get('date', '').strip()
        description  = request.POST.get('description', '').strip()

        errors = []
        if not student:
            errors.append('Nachwuchskraft ist erforderlich.')
        if not cat_pk:
            errors.append('Bitte eine Kategorie wählen.')
        if not trigger_type:
            errors.append('Bitte einen Auslöser angeben.')
        if not date_raw:
            errors.append('Datum ist erforderlich.')
        if not description:
            errors.append('Beschreibung / Gesprächsinhalt ist erforderlich.')

        category = None
        if cat_pk:
            try:
                category = InterventionCategory.objects.get(pk=cat_pk, is_active=True)
            except InterventionCategory.DoesNotExist:
                errors.append('Ungültige Kategorie.')

        # Datum parsen
        intervention_date = None
        if date_raw:
            try:
                from datetime import date as _date
                intervention_date = _date.fromisoformat(date_raw)
            except ValueError:
                errors.append('Ungültiges Datum.')

        # Folgetermin / Frist – Pflichtfeld wenn kategorie.requires_followup gesetzt ist
        followup_raw  = request.POST.get('followup_date', '').strip()
        followup_date = None
        if followup_raw:
            try:
                from datetime import date as _date
                followup_date = _date.fromisoformat(followup_raw)
            except ValueError:
                errors.append('Ungültige Frist.')
        elif category and category.requires_followup:
            errors.append(f'Kategorie „{category}" erfordert einen Folgetermin.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'intervention/intervention_create.html', {
                'student':    student,
                'categories': categories,
                'trigger_choices': TRIGGER_CHOICES,
                'post':       request.POST,
            })

        # Optionale verknüpfte Objekte (Krankmeldung oder Beurteilung)
        sick_leave = None
        assessment = None
        if trigger_type == TRIGGER_ABSENCE:
            sl_pk = request.POST.get('trigger_sick_leave')
            if sl_pk:
                sick_leave = SickLeave.objects.filter(pk=sl_pk, student=student).first()
        elif trigger_type == TRIGGER_ASSESSMENT:
            a_pk = request.POST.get('trigger_assessment')
            if a_pk:
                assessment = Assessment.objects.filter(pk=a_pk, assignment__student=student).first()

        participant_pks = request.POST.getlist('participants')

        intervention = Intervention.objects.create(
            student            = student,
            category           = category,
            trigger_type       = trigger_type,
            trigger_sick_leave = sick_leave,
            trigger_assessment = assessment,
            date               = intervention_date,
            description        = description,
            agreement          = request.POST.get('agreement', '').strip(),
            followup_date      = followup_date,
            created_by         = request.user,
        )

        if participant_pks:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            intervention.participants.set(
                User.objects.filter(pk__in=participant_pks)
            )

        messages.success(
            request,
            f'Maßnahme „{category}" für {student} wurde erfasst.',
        )
        return redirect('student:student_detail', pk=student.pk)

    # GET – Kontext für optionale verknüpfte Objekte aufbauen
    sick_leaves = []
    assessments = []
    if student:
        sick_leaves = SickLeave.objects.filter(student=student).order_by('-start_date')[:20]
        assessments = Assessment.objects.filter(
            assignment__student=student
        ).select_related('assignment__unit').order_by('-assignment__end_date')[:20]

    from django.contrib.auth import get_user_model
    staff_users = get_user_model().objects.filter(
        is_active=True
    ).exclude(pk=request.user.pk).order_by('last_name', 'first_name')

    return render(request, 'intervention/intervention_create.html', {
        'student':       student,
        'categories':    categories,
        'trigger_choices': TRIGGER_CHOICES,
        'sick_leaves':   sick_leaves,
        'assessments':   assessments,
        'staff_users':   staff_users,
        'post':          {},
    })


# ── Detail ────────────────────────────────────────────────────────────────────

@login_required
def intervention_detail(request, public_id):
    _require_referat(request)

    intervention = get_object_or_404(
        Intervention.objects.select_related(
            'student', 'category', 'created_by', 'closed_by',
            'trigger_sick_leave', 'trigger_assessment__assignment__unit',
            'follow_up', 'predecessor',
        ).prefetch_related('participants'),
        public_id=public_id,
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'set_status':
            new_status = request.POST.get('new_status')
            valid = [s[0] for s in STATUS_CHOICES]
            if new_status not in valid:
                messages.error(request, 'Ungültiger Status.')
                return redirect('intervention:detail', public_id=public_id)

            intervention.status = new_status
            if new_status == STATUS_CLOSED:
                intervention.outcome   = request.POST.get('outcome', '').strip()
                intervention.closed_at = timezone.now()
                intervention.closed_by = request.user
            intervention.save()
            messages.success(request, f'Status auf „{intervention.get_status_display()}" gesetzt.')
            return redirect('intervention:detail', public_id=public_id)

        if action == 'update_followup_date':
            followup_raw = request.POST.get('followup_date', '').strip()
            if followup_raw:
                try:
                    from datetime import date as _date
                    intervention.followup_date = _date.fromisoformat(followup_raw)
                    intervention.save(update_fields=['followup_date', 'updated_at'])
                    messages.success(request, 'Frist aktualisiert.')
                except ValueError:
                    messages.error(request, 'Ungültiges Datum.')
            else:
                intervention.followup_date = None
                intervention.save(update_fields=['followup_date', 'updated_at'])
                messages.success(request, 'Frist entfernt.')
            return redirect('intervention:detail', public_id=public_id)

    from services.roles import is_training_director
    can_delete = is_training_director(request.user)

    return render(request, 'intervention/intervention_detail.html', {
        'intervention': intervention,
        'status_choices': STATUS_CHOICES,
        'can_delete': can_delete,
        'today': date.today(),
    })


# ── Kategorien-Verwaltung ─────────────────────────────────────────────────────

def _require_leitung(request):
    """Prüft ob der Nutzer Ausbildungsleitung oder Staff ist."""
    from services.roles import is_training_director
    if not (is_training_director(request.user) or request.user.is_staff):
        raise PermissionDenied


@login_required
def category_list(request):
    _require_leitung(request)
    categories = InterventionCategory.objects.order_by('escalation_level', 'name')
    return render(request, 'intervention/category_settings.html', {
        'categories': categories,
    })


@login_required
def category_create(request):
    _require_leitung(request)
    if request.method == 'POST':
        name             = request.POST.get('name', '').strip()
        escalation_level = request.POST.get('escalation_level', '1')
        color            = request.POST.get('color', 'secondary')
        requires_followup = request.POST.get('requires_followup') == 'on'
        is_active        = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Bezeichnung ist erforderlich.')
        elif InterventionCategory.objects.filter(name=name).exists():
            messages.error(request, f'Eine Kategorie mit dem Namen „{name}" existiert bereits.')
        else:
            InterventionCategory.objects.create(
                name=name,
                escalation_level=int(escalation_level),
                color=color,
                requires_followup=requires_followup,
                is_active=is_active,
            )
            messages.success(request, f'Kategorie „{name}" wurde erstellt.')
        return redirect('intervention:category_list')
    return redirect('intervention:category_list')


@login_required
def category_edit(request, public_id):
    _require_leitung(request)
    category = get_object_or_404(InterventionCategory, public_id=public_id)
    if request.method == 'POST':
        name              = request.POST.get('name', '').strip()
        escalation_level  = request.POST.get('escalation_level', '1')
        color             = request.POST.get('color', 'secondary')
        requires_followup = request.POST.get('requires_followup') == 'on'
        is_active         = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Bezeichnung ist erforderlich.')
        elif InterventionCategory.objects.filter(name=name).exclude(public_id=public_id).exists():
            messages.error(request, f'Eine Kategorie mit dem Namen „{name}" existiert bereits.')
        else:
            category.name              = name
            category.escalation_level  = int(escalation_level)
            category.color             = color
            category.requires_followup = requires_followup
            category.is_active         = is_active
            category.save()
            messages.success(request, f'Kategorie „{name}" wurde gespeichert.')
        return redirect('intervention:category_list')
    return redirect('intervention:category_list')


@login_required
@require_POST
def category_delete(request, public_id):
    _require_leitung(request)
    category = get_object_or_404(InterventionCategory, public_id=public_id)
    if category.interventions.exists():
        messages.error(
            request,
            f'Kategorie „{category}" kann nicht gelöscht werden – sie wird von '
            f'{category.interventions.count()} Maßnahme(n) verwendet.',
        )
    else:
        name = str(category)
        category.delete()
        messages.success(request, f'Kategorie „{name}" wurde gelöscht.')
    return redirect('intervention:category_list')


# ── Löschen ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
def intervention_delete(request, public_id):
    from services.roles import is_training_director
    if not is_training_director(request.user):
        raise PermissionDenied

    intervention = get_object_or_404(Intervention, public_id=public_id)
    student_pk   = intervention.student_id
    category_name = str(intervention.category)
    intervention.delete()
    messages.success(request, f'Maßnahme „{category_name}" wurde gelöscht.')
    return redirect('student:student_detail', public_id=student_pk)
