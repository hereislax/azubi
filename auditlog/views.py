# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für das Audit-Log (globale Protokollansicht und nachwuchskraftbezogenes Protokoll)."""
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from services.roles import training_director_required
from .models import AuditLogEntry

# Lesbare Modellbezeichnungen für das Filter-Dropdown
MODEL_LABELS = {
    'student':              'Nachwuchskraft',
    'grade':                'Note',
    'course':               'Kurs',
    'scheduleblock':        'Ablaufblock',
    'internshipassignment': 'Praktikumseinsatz',
    'trainingrecord':       'Ausbildungsnachweis',
    'roomassignment':       'Wohnheim-Belegung',
    'assessment':           'Beurteilung',
    'assessmentrating':     'Kriteriumbewertung',
    'assessmenttemplate':   'Beurteilungsvorlage',
    'assessmentcriterion':  'Beurteilungskriterium',
    'trainingtype':         'Schulungs-Typ',
    'trainingcompletion':   'Schulungs-Teilnahme',
    'instructor':           'Praxistutor',
    'chiefinstructor':      'Person (Ausbildungskoordination)',
    'trainingcoordination': 'Ausbildungskoordination',
    'inventoryitem':        'Inventargegenstand',
    'inventoryissuance':    'Inventarausgabe',
    'inventorycategory':    'Inventar-Kategorie',
    'vacationrequest':      'Urlaubsantrag',
    'sickleave':            'Krankmeldung',
    'absencesettings':      'Abwesenheitseinstellungen',
}


@training_director_required
def auditlog_list(request):
    """Globale Audit-Log-Ansicht mit Filter nach Modell, Aktion, Nutzer und Zeitraum."""
    qs = AuditLogEntry.objects.select_related('user')

    # ── Filter: model_name ────────────────────────────────────────────────────
    model_filter = request.GET.get('model', '')
    if model_filter:
        qs = qs.filter(model_name=model_filter)

    # ── Filter: action ────────────────────────────────────────────────────────
    action_filter = request.GET.get('action', '')
    if action_filter:
        qs = qs.filter(action=action_filter)

    # ── Filter: user ──────────────────────────────────────────────────────────
    user_filter = request.GET.get('user', '')
    if user_filter:
        qs = qs.filter(user_id=user_filter)

    # ── Filter: date_from / date_to ───────────────────────────────────────────
    date_from = request.GET.get('date_from', '')
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)

    date_to = request.GET.get('date_to', '')
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)

    # ── Filter: search (object_repr) ──────────────────────────────────────────
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(object_repr__icontains=search)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    users_with_entries = User.objects.filter(
        audit_log_entries__isnull=False
    ).distinct().order_by('last_name', 'first_name', 'username')

    return render(request, 'auditlog/auditlog_list.html', {
        'page_obj': page_obj,
        'model_labels': MODEL_LABELS,
        'model_filter': model_filter,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
        'users_with_entries': users_with_entries,
        'action_choices': AuditLogEntry.ACTION_CHOICES,
        'total_count': qs.count(),
    })


@training_director_required
def auditlog_student(request, student_id):
    """Audit-Log gefiltert auf eine einzelne Nachwuchskraft."""
    from student.models import Student
    student = get_object_or_404(Student, pk=student_id)

    qs = AuditLogEntry.objects.filter(
        student_id=str(student_id)
    ).select_related('user').order_by('-timestamp')

    return render(request, 'auditlog/auditlog_student.html', {
        'student': student,
        'entries': qs,
    })
