# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für Praxistutoren, Ausbildungskoordinationen und Praktikumseinsatz-Verwaltung."""
import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Instructor, ChiefInstructor, TrainingCoordination
from .forms import InstructorForm, ChiefInstructorForm, TrainingCoordinationForm


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _collect_descendant_pks(root_pk: int, children_map: dict) -> list[int]:
    """Sammelt alle Nachkommen-PKs einer Organisationseinheit rekursiv."""
    result = [root_pk]
    for child_pk in children_map.get(root_pk, []):
        result.extend(_collect_descendant_pks(child_pk, children_map))
    return result


def _build_unit_subtree(unit, children_map, all_units_by_pk):
    """Baut einen verschachtelten Baum aus Organisationseinheiten auf."""
    return {
        'unit': unit,
        'children': [
            _build_unit_subtree(all_units_by_pk[child_pk], children_map, all_units_by_pk)
            for child_pk in children_map.get(unit.pk, [])
        ],
    }


def _get_coordination_area(coordination):
    """Gibt (descendant_pks, children_map, all_units_by_pk) für eine Koordination zurück."""
    from organisation.models import OrganisationalUnit
    all_units = list(OrganisationalUnit.objects.only('pk', 'parent_id', 'name', 'label', 'unit_type', 'is_active'))
    all_units_by_pk = {u.pk: u for u in all_units}
    children_map: dict[int, list[int]] = {u.pk: [] for u in all_units}
    for u in all_units:
        if u.parent_id and u.parent_id in children_map:
            children_map[u.parent_id].append(u.pk)

    assigned_pks = set(coordination.units.values_list('pk', flat=True))
    descendant_pks = []
    for pk in assigned_pks:
        descendant_pks.extend(_collect_descendant_pks(pk, children_map))
    descendant_pks = list(dict.fromkeys(descendant_pks))

    return descendant_pks, children_map, all_units_by_pk


def _require_coordination_member(request, coordination):
    """
    Wirft PermissionDenied, wenn eine eingeloggte Ausbildungskoordination
    kein Mitglied dieser Koordination ist.
    """
    from django.core.exceptions import PermissionDenied
    from services.roles import is_training_coordinator, get_chief_instructor

    if request.user.is_authenticated and is_training_coordinator(request.user):
        chief = get_chief_instructor(request.user)
        if not chief or chief.coordination_id != coordination.pk:
            raise PermissionDenied


# ── Praxistutor-Views ────────────────────────────────────────────────────────
@login_required
def instructor_list(request):
    from services.roles import is_training_director, is_training_coordinator, get_chief_instructor

    qs = Instructor.objects.select_related('unit', 'salutation').prefetch_related('job_profiles')

    # Ausbildungskoordination sieht nur Praxistutoren im eigenen Bereich
    if is_training_coordinator(request.user):
        chief = get_chief_instructor(request.user)
        if chief and chief.coordination:
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)
            qs = qs.filter(unit_id__in=descendant_pks)
        else:
            qs = qs.none()

    return render(request, 'instructor/instructor_list.html', {
        'instructors': qs,
        'can_confirm': is_training_director(request.user),
    })

@login_required
def instructor_detail(request, public_id):
    from course.models import InternshipAssignment
    from django.core.exceptions import PermissionDenied
    from services.roles import is_training_coordinator, get_chief_instructor

    instructor = get_object_or_404(
        Instructor.objects.select_related('unit', 'salutation').prefetch_related('job_profiles'),
        public_id=public_id,
    )

    # Bereichsprüfung für Ausbildungskoordinationen
    if is_training_coordinator(request.user):
        chief = get_chief_instructor(request.user)
        if chief and chief.coordination:
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)
            if instructor.unit_id not in descendant_pks:
                raise PermissionDenied
        else:
            raise PermissionDenied

    today = date.today()
    all_assignments = list(
        InternshipAssignment.objects
        .filter(instructor=instructor)
        .select_related('student', 'unit', 'schedule_block')
        .order_by('student__last_name', 'student__first_name')
    )
    current_assignments = [a for a in all_assignments if a.start_date <= today <= a.end_date]
    past_assignments    = sorted([a for a in all_assignments if a.end_date < today],    key=lambda a: a.end_date,   reverse=True)
    future_assignments  = sorted([a for a in all_assignments if a.start_date > today],  key=lambda a: a.start_date)

    from services.roles import is_training_director
    return render(request, 'instructor/instructor_detail.html', {
        'instructor': instructor,
        'current_assignments': current_assignments,
        'past_assignments':    past_assignments,
        'future_assignments':  future_assignments,
        'can_confirm': is_training_director(request.user),
    })


def _location_queryset_for_unit(unit):
    """Gibt das Location-Queryset für eine Organisationseinheit zurück (eigene + vererbte)."""
    from organisation.models import Location
    if unit is None:
        return Location.objects.all().select_related('address')
    return unit.get_all_locations().select_related('address')


@login_required
def instructor_create(request):
    from services.roles import is_training_coordinator, get_chief_instructor

    unit_queryset = None
    # Ausbildungskoordination: nur Einheiten im eigenen Bereich anbieten
    if is_training_coordinator(request.user):
        from organisation.models import OrganisationalUnit
        chief = get_chief_instructor(request.user)
        if chief and chief.coordination:
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)
            unit_queryset = OrganisationalUnit.objects.filter(
                pk__in=descendant_pks, is_active=True
            ).order_by('unit_type', 'name')
        else:
            unit_queryset = OrganisationalUnit.objects.none()

    # Gewählte Einheit für Standortfilterung (aus POST oder leer)
    selected_unit = None
    if request.POST.get('unit'):
        from organisation.models import OrganisationalUnit
        selected_unit = OrganisationalUnit.objects.filter(pk=request.POST['unit']).first()

    form = InstructorForm(
        request.POST or None,
        unit_queryset=unit_queryset,
        location_queryset=_location_queryset_for_unit(selected_unit),
    )
    if form.is_valid():
        instructor = form.save(commit=False)
        instructor.status = Instructor.PENDING
        instructor.save()
        form.save_m2m()
        from django.urls import reverse
        from services.models import notify_staff
        notify_staff(
            message=f'Neuer Praxistutor zur Bestätigung: {instructor.first_name} {instructor.last_name} – {instructor.unit}',
            link=reverse('instructor:instructor_detail', kwargs={'public_id': instructor.public_id}),
            icon='bi-person-check',
            category='Praxistutor',
        )
        messages.success(request, f'„{instructor}" wurde angelegt und wartet auf Bestätigung durch die Ausbildungsleitung.')
        return redirect('instructor:instructor_detail', public_id=instructor.public_id)
    return render(request, 'instructor/instructor_form.html', {'form': form, 'action': 'Anlegen'})


@login_required
def instructor_confirm(request, public_id):
    """Bestätigungsview: Ausbildungsleitung bestätigt einen neuen Praxistutor."""
    import threading
    import logging
    from instructor.models import INSTRUCTOR_STATUS_CONFIRMED

    instructor = get_object_or_404(Instructor, public_id=public_id)

    if not request.user.is_staff and not request.user.groups.filter(name='ausbildungsleitung').exists():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if request.method == 'POST':
        instructor.status = INSTRUCTOR_STATUS_CONFIRMED
        instructor.save(update_fields=['status'])

        # E-Mail im Hintergrund versenden, damit die Weiterleitung sofort erfolgt
        detail_url = request.build_absolute_uri(f'/praxistutoren/{instructor.public_id}/')
        logger = logging.getLogger(__name__)
        creator_user = request.user

        def _send():
            try:
                from services.notifications import notify_instructor_confirmed
                notify_instructor_confirmed(instructor, detail_url, creator=creator_user)
                logger.info('Bestellungsschreiben für Praxistutor public_id=%s gesendet', public_id)
            except Exception as exc:
                logger.error('Bestellungsschreiben für Praxistutor public_id=%s fehlgeschlagen: %s', public_id, exc)

        threading.Thread(target=_send, daemon=True).start()

        messages.success(request, f'„{instructor}" wurde bestätigt. Das Bestellungsschreiben wird im Hintergrund versendet.')
        return redirect('instructor:instructor_detail', public_id=instructor.public_id)

    return render(request, 'instructor/instructor_confirm.html', {'instructor': instructor})


@login_required
def instructor_edit(request, public_id):
    instructor = get_object_or_404(Instructor, public_id=public_id)
    # Gewählte Einheit aus POST oder bestehende Einheit verwenden
    if request.POST.get('unit'):
        from organisation.models import OrganisationalUnit
        selected_unit = OrganisationalUnit.objects.filter(public_id=request.POST['unit']).first()
    else:
        selected_unit = instructor.unit

    form = InstructorForm(
        request.POST or None,
        instance=instructor,
        location_queryset=_location_queryset_for_unit(selected_unit),
    )
    if form.is_valid():
        form.save()
        messages.success(request, f'„{instructor}" wurde erfolgreich gespeichert.')
        return redirect('instructor:instructor_detail', public_id=instructor.public_id)
    return render(request, 'instructor/instructor_form.html', {
        'form': form,
        'action': 'Bearbeiten',
        'instructor': instructor,
    })


@login_required
def instructor_delete(request, public_id):
    instructor = get_object_or_404(Instructor, public_id=public_id)
    if request.method == 'POST':
        name = str(instructor)
        instructor.delete()
        messages.success(request, f'„{name}" wurde gelöscht.')
        return redirect('instructor:instructor_list')
    return render(request, 'instructor/instructor_confirm_delete.html', {'instructor': instructor})


# ── Koordination-Views ───────────────────────────────────────────────────────
@login_required
def chief_instructor_list(request):
    """Liste aller Ausbildungskoordinationen mit zugewiesenen Einheiten und Mitgliedern."""
    coordinations = TrainingCoordination.objects.prefetch_related('units', 'members')
    return render(request, 'instructor/chief_instructor_list.html', {'koordinationen': coordinations})

@login_required
def chief_instructor_detail(request, public_id):
    """Detailseite einer Ausbildungskoordination mit Einsaetzen und Praxistutoren."""
    from course.models import InternshipAssignment

    coordination = get_object_or_404(
        TrainingCoordination.objects.prefetch_related('units', 'members__salutation', 'members__user'),
        public_id=public_id,
    )
    _require_coordination_member(request, coordination)

    descendant_pks, children_map, all_units_by_pk = _get_coordination_area(coordination)

    assigned_pks = set(coordination.units.values_list('public_id', flat=True))
    unit_trees = [
        _build_unit_subtree(all_units_by_pk[root_pk], children_map, all_units_by_pk)
        for root_pk in assigned_pks
        if root_pk in all_units_by_pk
    ]

    all_assignments = list(
        InternshipAssignment.objects
        .filter(unit_id__in=descendant_pks)
        .select_related('student', 'unit', 'schedule_block', 'created_by')
        .order_by('student__last_name', 'student__first_name')
    )

    today = date.today()
    current_assignments = [a for a in all_assignments if a.start_date <= today <= a.end_date]
    past_assignments = sorted([a for a in all_assignments if a.end_date < today], key=lambda a: a.end_date, reverse=True)
    future_assignments = sorted([a for a in all_assignments if a.start_date > today], key=lambda a: a.start_date)
    pending_assignments = sorted(
        [a for a in all_assignments if a.status == 'pending'],
        key=lambda a: a.start_date,
    )

    area_instructors = list(
        Instructor.objects
        .filter(unit_id__in=descendant_pks)
        .select_related('unit', 'salutation')
        .prefetch_related('job_profiles')
        .order_by('unit__name', 'last_name', 'first_name')
    )
    pending_instructors   = [i for i in area_instructors if i.status == Instructor.PENDING]
    confirmed_instructors = [i for i in area_instructors if i.status == Instructor.CONFIRMED]

    from services.roles import is_training_coordinator, is_training_director
    return render(request, 'instructor/chief_instructor_detail.html', {
        'chief': coordination,
        'coordination': coordination,
        'coordination': coordination,
        'unit_trees': unit_trees,
        'current_assignments': current_assignments,
        'past_assignments': past_assignments,
        'future_assignments': future_assignments,
        'pending_assignments': pending_assignments,
        'area_instructors':      area_instructors,
        'pending_instructors':   pending_instructors,
        'confirmed_instructors': confirmed_instructors,
        'is_training_coordinator': is_training_coordinator(request.user),
        'can_confirm': is_training_director(request.user),
    })


@login_required
def chief_instructor_create(request):
    form = TrainingCoordinationForm(request.POST or None)
    if form.is_valid():
        coordination = form.save()
        messages.success(request, f'„{coordination}" wurde erfolgreich angelegt.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    return render(request, 'instructor/chief_instructor_form.html', {'form': form, 'action': 'Anlegen'})


@login_required
def chief_instructor_edit(request, public_id):
    coordination = get_object_or_404(TrainingCoordination, public_id=public_id)
    form = TrainingCoordinationForm(request.POST or None, instance=coordination)
    if form.is_valid():
        form.save()
        messages.success(request, f'„{coordination}" wurde erfolgreich gespeichert.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    return render(request, 'instructor/chief_instructor_form.html', {
        'form': form,
        'action': 'Bearbeiten',
        'chief': coordination,
    })


@login_required
def chief_instructor_delete(request, public_id):
    coordination = get_object_or_404(TrainingCoordination, public_id=public_id)
    if request.method == 'POST':
        name = str(coordination)
        coordination.delete()
        messages.success(request, f'„{name}" wurde gelöscht.')
        return redirect('instructor:chief_instructor_list')
    return render(request, 'instructor/chief_instructor_confirm_delete.html', {'chief': coordination})


# ── Mitglieder (ChiefInstructor) der Koordination ────────────────────────────
@login_required
def _create_chief_user_and_notify(request, chief, coordination):
    """Legt ein Django-Benutzerkonto für den ChiefInstructor an und sendet eine Willkommens-E-Mail."""
    from django.contrib.auth.models import User, Group
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes

    if not chief.email or chief.user_id:
        return

    username = chief.email.split('@')[0]
    base = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}_{counter}"
        counter += 1

    user = User.objects.create(
        username=username,
        email=chief.email,
        first_name=chief.first_name,
        last_name=chief.last_name,
    )
    user.set_unusable_password()
    user.save()

    group, _ = Group.objects.get_or_create(name='ausbildungskoordination')
    user.groups.add(group)

    chief.user = user
    chief.save(update_fields=['user'])

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    set_password_url = request.build_absolute_uri(f'/accounts/reset/{uid}/{token}/')

    try:
        from services.email import send_mail
        from services.models import NotificationTemplate
        subject, body = NotificationTemplate.render('chief_welcome', {
            'vorname':      chief.first_name,
            'nachname':     chief.last_name,
            'benutzername': user.username,
            'passwort_url': set_password_url,
        })
        send_mail(subject=subject, body_text=body, recipient_list=[chief.email])
        messages.info(request, f'Benutzerkonto angelegt und Willkommens-E-Mail an {chief.email} gesendet.')
    except Exception as exc:
        messages.warning(request, f'Benutzerkonto angelegt, aber E-Mail konnte nicht gesendet werden: {exc}')


@login_required
def member_create(request, koordination_public_id):
    coordination = get_object_or_404(TrainingCoordination, pk=koordination_public_id)
    form = ChiefInstructorForm(request.POST or None, initial={'coordination': coordination})
    if form.is_valid():
        chief = form.save(commit=False)
        chief.coordination = coordination
        chief.save()
        _create_chief_user_and_notify(request, chief, coordination)
        messages.success(request, f'„{chief}" wurde erfolgreich hinzugefügt.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    return render(request, 'instructor/chief_instructor_member_form.html', {
        'form': form,
        'coordination': coordination,
        'action': 'Hinzufügen',
    })


@login_required
def member_edit(request, koordination_public_id, member_public_id):
    coordination = get_object_or_404(TrainingCoordination, pk=koordination_public_id)
    chief = get_object_or_404(ChiefInstructor, pk=member_public_id, coordination=coordination)
    form = ChiefInstructorForm(request.POST or None, instance=chief)
    if form.is_valid():
        form.save()
        messages.success(request, f'„{chief}" wurde gespeichert.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    return render(request, 'instructor/chief_instructor_member_form.html', {
        'form': form,
        'coordination': coordination,
        'chief': chief,
        'action': 'Bearbeiten',
    })


@login_required
def member_delete(request, koordination_public_id, member_public_id):
    coordination = get_object_or_404(TrainingCoordination, pk=koordination_public_id)
    chief = get_object_or_404(ChiefInstructor, pk=member_public_id, coordination=coordination)
    if request.method == 'POST':
        name = str(chief)
        user = chief.user
        chief.delete()
        if user:
            user.delete()
        messages.success(request, f'„{name}" und das zugehörige Benutzerkonto wurden gelöscht.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    return render(request, 'instructor/chief_instructor_member_confirm_delete.html', {
        'chief': chief,
        'coordination': coordination,
    })


@login_required
def member_create_user(request, koordination_public_id, member_public_id):
    coordination = get_object_or_404(TrainingCoordination, pk=koordination_public_id)
    chief = get_object_or_404(ChiefInstructor, pk=member_public_id, coordination=coordination)
    if chief.user_id:
        messages.info(request, f'„{chief}" hat bereits ein Benutzerkonto.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    if request.method == 'POST':
        _create_chief_user_and_notify(request, chief, coordination)
        chief.refresh_from_db()
        if chief.user_id:
            messages.success(request, f'Benutzerkonto für „{chief}" wurde angelegt.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)
    return render(request, 'instructor/chief_instructor_create_user_confirm.html', {
        'chief': chief,
        'coordination': coordination,
    })


# ── Kalender ──────────────────────────────────────────────────────────────────

from services.colors import BUNDESFARBEN_PALETTE as ASSIGNMENT_COLORS  # noqa: E402

@login_required
def chief_instructor_calendar(request, public_id):
    """Jahreskalender einer Ausbildungskoordination mit allen Praktikumseinsaetzen."""
    from datetime import date, timedelta
    from course.models import InternshipAssignment

    coordination = get_object_or_404(TrainingCoordination, public_id=public_id)
    _require_coordination_member(request, coordination)
    descendant_pks, children_map, all_units_by_pk = _get_coordination_area(coordination)

    year = int(request.GET.get('year', date.today().year))
    year_start = date(year, 1, 1)
    year_end   = date(year, 12, 31)
    year_days  = (year_end - year_start).days + 1

    months_data = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end = date(year, m + 1, 1) - timedelta(days=1) if m < 12 else year_end
        m_days = (m_end - m_start).days + 1
        months_data.append({
            'name':   m_start.strftime('%B'),
            'short':  m_start.strftime('%b'),
            'days':   m_days,
            'offset': f'{(m_start - year_start).days / year_days * 100:.6f}',
            'width':  f'{m_days / year_days * 100:.6f}',
        })

    today = date.today()
    today_offset = None
    if year_start <= today <= year_end:
        today_offset = f'{(today - year_start).days / year_days * 100:.4f}'

    all_assignments = (
        InternshipAssignment.objects
        .filter(unit_id__in=descendant_pks, start_date__lte=year_end, end_date__gte=year_start)
        .select_related('student', 'unit', 'schedule_block')
        .order_by('unit_id', 'start_date')
    )
    by_unit: dict[int, list] = {public_id: [] for public_id in descendant_pks}
    for a in all_assignments:
        by_unit[a.unit_id].append(a)

    bar_height  = 38
    bar_gap     = 6
    row_padding = 6

    units_data = []
    for unit_pk in descendant_pks:
        unit = all_units_by_pk.get(unit_pk)
        if unit is None:
            continue
        assignments_raw = by_unit[unit_pk]
        assignments_data = []
        for a in assignments_raw:
            clip_start = max(a.start_date, year_start)
            clip_end   = min(a.end_date, year_end)
            if clip_start > clip_end:
                continue
            raw_offset = (clip_start - year_start).days / year_days * 100
            raw_width  = max(((clip_end - clip_start).days + 1) / year_days * 100, 0.3)
            assignments_data.append({
                'assignment': a,
                'offset':    f'{raw_offset:.4f}',
                'width':     f'{raw_width:.4f}',
                'raw_offset': raw_offset,
                'raw_end':    raw_offset + raw_width,
                'label':     f'{a.student.first_name} {a.student.last_name}',
                'start_fmt': a.start_date.strftime('%d.%m.%Y'),
                'end_fmt':   a.end_date.strftime('%d.%m.%Y'),
            })

        # Spurzuweisung: Einsaetze werden so platziert, dass sie sich nicht ueberlappen
        lane_ends = []
        for a_data in assignments_data:
            placed = False
            for i, end in enumerate(lane_ends):
                if a_data['raw_offset'] >= end:
                    lane_ends[i] = a_data['raw_end']
                    a_data['lane'] = i
                    placed = True
                    break
            if not placed:
                a_data['lane'] = len(lane_ends)
                lane_ends.append(a_data['raw_end'])

        # Farbzuweisung: ueberlappende Einsaetze erhalten unterschiedliche Farben
        for i, a_data in enumerate(assignments_data):
            used = {
                other['color_idx'] for other in assignments_data[:i]
                if a_data['raw_offset'] < other['raw_end'] and a_data['raw_end'] > other['raw_offset']
            }
            preferred = hash(str(a_data['assignment'].student_id)) % len(ASSIGNMENT_COLORS)
            color_idx = preferred
            while color_idx in used:
                color_idx = (color_idx + 1) % len(ASSIGNMENT_COLORS)
            a_data['color_idx'] = color_idx
            a_data['color'] = ASSIGNMENT_COLORS[color_idx]

        num_lanes  = max(len(lane_ends), 1)
        row_height = bar_gap + num_lanes * (bar_height + bar_gap) + row_padding
        for a_data in assignments_data:
            a_data['top_px'] = bar_gap + a_data['lane'] * (bar_height + bar_gap)

        units_data.append({
            'unit':        unit,
            'assignments': assignments_data,
            'row_height':  row_height,
        })

    return render(request, 'instructor/chief_instructor_calendar.html', {
        'chief':          coordination,
        'year':           year,
        'prev_year':      year - 1,
        'next_year':      year + 1,
        'months_data':    months_data,
        'today_offset':   today_offset,
        'year_days':      year_days,
        'year_start_iso': year_start.isoformat(),
        'units_data':     units_data,
    })


# ── Einsatz-Aktionen (Koordination) ─────────────────────────────────────────
def _coordination_assignment_or_403(coordination, assignment_pk):
    """Laedt einen Praktikumseinsatz und prueft, ob er im Bereich der Koordination liegt."""
    from course.models import InternshipAssignment
    from django.core.exceptions import PermissionDenied

    assignment = get_object_or_404(
        InternshipAssignment.objects.select_related('student', 'unit', 'schedule_block', 'created_by'),
        pk=assignment_pk,
    )
    descendant_pks, _, _ = _get_coordination_area(coordination)
    if assignment.unit_id not in descendant_pks:
        raise PermissionDenied
    return assignment


@login_required
def chief_instructor_approve_assignment(request, chief_public_id, assignment_pk):
    """Ausbildungskoordination nimmt einen Praktikumseinsatz an."""
    from course.models import ASSIGNMENT_STATUS_APPROVED

    coordination = get_object_or_404(TrainingCoordination, pk=chief_public_id)
    _require_coordination_member(request, coordination)
    assignment = _coordination_assignment_or_403(coordination, assignment_pk)

    if request.method == 'POST':
        assignment.status = ASSIGNMENT_STATUS_APPROVED
        assignment.rejection_reason = ''
        assignment.save(update_fields=['status', 'rejection_reason'])
        from services.notifications import (
            notify_creator_of_decision,
            notify_training_office_of_assignment_decision,
        )
        notify_creator_of_decision(request, assignment)
        notify_training_office_of_assignment_decision(request, assignment)
        messages.success(request, f'Einsatz für {assignment.student} wurde angenommen.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)

    return render(request, 'instructor/chief_instructor_assignment_review.html', {
        'chief': coordination,
        'assignment': assignment,
        'action': 'approve',
    })


@login_required
def chief_instructor_reject_assignment(request, chief_public_id, assignment_pk):
    """Ausbildungskoordination lehnt einen Praktikumseinsatz ab."""
    from course.models import ASSIGNMENT_STATUS_REJECTED

    coordination = get_object_or_404(TrainingCoordination, pk=chief_public_id)
    _require_coordination_member(request, coordination)
    assignment = _coordination_assignment_or_403(coordination, assignment_pk)

    if request.method == 'POST':
        assignment.status = ASSIGNMENT_STATUS_REJECTED
        assignment.rejection_reason = request.POST.get('reason', '').strip()
        assignment.save(update_fields=['status', 'rejection_reason'])
        from services.notifications import (
            notify_creator_of_decision,
            notify_training_office_of_assignment_decision,
        )
        notify_creator_of_decision(request, assignment)
        notify_training_office_of_assignment_decision(request, assignment)
        messages.success(request, f'Einsatz für {assignment.student} wurde abgelehnt.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)

    return render(request, 'instructor/chief_instructor_assignment_review.html', {
        'chief': coordination,
        'assignment': assignment,
        'action': 'reject',
    })


@login_required
def chief_instructor_assignment_edit(request, chief_public_id, assignment_pk):
    """Bearbeitung eines Praktikumseinsatzes durch die Ausbildungskoordination."""
    from course.models import InternshipAssignment
    from course.forms import InternshipAssignmentForm
    from course.views import _get_unit_capacity_info
    from organisation.models import OrganisationalUnit

    coordination = get_object_or_404(TrainingCoordination, pk=chief_public_id)
    _require_coordination_member(request, coordination)
    assignment = get_object_or_404(
        InternshipAssignment.objects.select_related('student__course'), pk=assignment_pk
    )
    previous_instructor_id = assignment.instructor_id
    block = assignment.schedule_block
    student = assignment.student

    descendant_pks, children_map, all_units_by_pk = _get_coordination_area(coordination)
    unit_queryset = OrganisationalUnit.objects.filter(
        pk__in=descendant_pks, is_active=True
    ).order_by('unit_type', 'name')

    # Standortfilterung: nur Einheiten anzeigen, die zum Standort des Einsatzes passen
    if assignment.location_id:
        direct_loc_pks = set(assignment.location.units.values_list('pk', flat=True))
        valid_for_location: set[int] = set()
        for pk in direct_loc_pks:
            valid_for_location.update(_collect_descendant_pks(pk, children_map))
        allowed_pks = set(descendant_pks) & valid_for_location
        unit_queryset = unit_queryset.filter(pk__in=allowed_pks)

    full_pks, usage_map = _get_unit_capacity_info(block, exclude_assignment_pk=assignment.pk,
                                                   start_date=assignment.start_date, end_date=assignment.end_date)
    area_full_pks = full_pks & set(descendant_pks)

    # Solange der Einsatz noch nicht von der Koordination angenommen wurde,
    # darf sie alle Felder frei bearbeiten. Erst nach Annahme greifen die
    # ChangeRequest-Schranken (unit/dates/location nur via Antrag aenderbar).
    from course.models import ASSIGNMENT_STATUS_APPROVED
    is_locked_for_changes = assignment.status == ASSIGNMENT_STATUS_APPROVED

    form = InternshipAssignmentForm(
        request.POST or None,
        instance=assignment,
        block=block,
        full_unit_pks=full_pks,
        unit_queryset=unit_queryset,
        readonly_dates=is_locked_for_changes,
        student=student,
        location_readonly=is_locked_for_changes,
        student_readonly=True,
        unit_readonly=is_locked_for_changes,
    )
    if form.is_valid():
        form.save()
        assignment.refresh_from_db()
        # Bei Änderung des Praxistutors Benachrichtigung senden
        if assignment.instructor_id and assignment.instructor_id != previous_instructor_id:
            assignment.bump_notification_sequence()
            from services.notifications import notify_instructor_of_assignment
            notify_instructor_of_assignment(request, assignment)
        messages.success(request, f'Praktikumseinsatz für {assignment.student} wurde gespeichert.')
        return redirect('instructor:chief_instructor_detail', public_id=coordination.public_id)

    job_profile_pk = student.course.job_profile_id if student.course else None

    return render(request, 'instructor/chief_instructor_assignment_form.html', {
        'form': form,
        'chief': coordination,
        'assignment': assignment,
        'schedule_block': block,
        'full_unit_pks_json': json.dumps(list(area_full_pks)),
        'usage_map_json': json.dumps({str(k): v for k, v in usage_map.items() if k in descendant_pks}),
        'job_profile_pk': job_profile_pk,
        'is_locked_for_changes': is_locked_for_changes,
    })


# ── Statistik ─────────────────────────────────────────────────────────────────

@login_required
def instructor_statistics(request):
    """Statistik-Uebersicht: Praxistutoren nach Status, Einheit, Berufsbild und Auslastung."""
    from collections import Counter
    from datetime import date as _date
    from course.models import InternshipAssignment

    all_instructors = list(
        Instructor.objects
        .select_related('unit', 'location')
        .prefetch_related('job_profiles')
        .all()
    )
    confirmed = [i for i in all_instructors if i.status == Instructor.CONFIRMED]
    pending   = [i for i in all_instructors if i.status == Instructor.PENDING]

    # Aktuelle Betreuungen (heute laufende Einsätze mit Praxistutor)
    today = _date.today()
    active_assignments_qs = (
        InternshipAssignment.objects
        .filter(instructor__isnull=False, start_date__lte=today, end_date__gte=today)
        .select_related('instructor', 'student', 'unit')
        .order_by('instructor__last_name', 'instructor__first_name')
    )
    active_count = active_assignments_qs.count()

    # Aufteilung nach Status
    status_data = {
        'labels': ['Bestätigt', 'Ausstehend'],
        'values': [len(confirmed), len(pending)],
    }

    # Aufteilung nach Organisationseinheit
    unit_counts = Counter(
        (i.unit.name if i.unit else 'Keine Einheit') for i in all_instructors
    )

    # Aufteilung nach Berufsbild (M2M — ein Praxistutor kann mehrere haben)
    jp_counts: Counter = Counter()
    for i in all_instructors:
        profiles = list(i.job_profiles.all())
        if profiles:
            for jp in profiles:
                jp_counts[jp.job_profile] += 1
        else:
            jp_counts['Kein Berufsbild'] += 1

    # Aufteilung nach Standort
    location_counts = Counter(
        (i.location.name if i.location else 'Kein Standort') for i in all_instructors
    )

    # Auslastung pro Praxistutor (aktuell + nächste 4 Wochen)
    from datetime import timedelta
    import collections

    # Aktive Zuweisungen nach Praxistutor-ID gruppieren
    assignments_by_instructor: dict = collections.defaultdict(list)
    for a in active_assignments_qs:
        assignments_by_instructor[a.instructor_id].append(a)

    MAX_SUPERVISED = 5  # Limit aus der Formularvalidierung
    workload = []
    for instructor in confirmed:
        current_assignments = assignments_by_instructor.get(instructor.pk, [])
        count = len(current_assignments)
        workload.append({
            'instructor': instructor,
            'count': count,
            'assignments': current_assignments,
            'pct': min(int(count / MAX_SUPERVISED * 100), 100),
            'at_max': count >= MAX_SUPERVISED,
        })
    workload.sort(key=lambda x: (-x['count'], x['instructor'].last_name))

    # Top-Supervisors für Chart
    supervised_counts: Counter = Counter()
    for a in active_assignments_qs:
        supervised_counts[str(a.instructor)] += 1
    top_supervisors = supervised_counts.most_common(15)

    def chart_data(counter, top_n=None):
        items = sorted(counter.items(), key=lambda x: -x[1])
        if top_n:
            items = items[:top_n]
        return {'labels': [k for k, _ in items], 'values': [v for _, v in items]}

    return render(request, 'instructor/instructor_statistics.html', {
        'total':        len(all_instructors),
        'confirmed':    len(confirmed),
        'pending':      len(pending),
        'active_count': active_count,
        'status_data':  status_data,
        'unit_data':    chart_data(unit_counts, top_n=20),
        'jp_data':      chart_data(jp_counts),
        'location_data': chart_data(location_counts, top_n=20),
        'top_supervisors': top_supervisors,
        'workload':     workload,
        'max_supervised': MAX_SUPERVISED,
    })


# ── Änderungsanträge ──────────────────────────────────────────────────────────

@login_required
def change_request_create(request, chief_public_id, assignment_pk, change_type):
    """Koordination stellt einen Änderungsantrag für einen Praktikumseinsatz.

    Der Praxistutor-Wechsel (``instructor``) wird sofort wirksam, alle anderen
    Änderungstypen warten auf Genehmigung durch die Ausbildungsleitung.
    """
    from django.core.exceptions import PermissionDenied, ValidationError
    from course.models import (
        InternshipAssignment, AssignmentChangeRequest,
        CHANGE_REQUEST_STATUS_PENDING, CHANGE_REQUEST_STATUS_APPROVED,
        CHANGE_TYPE_CHOICES, CHANGE_TYPE_INSTRUCTOR,
    )
    from course.change_request_forms import get_form_class
    from course.change_handlers import apply_change_request

    coordination = get_object_or_404(TrainingCoordination, pk=chief_public_id)
    _require_coordination_member(request, coordination)
    assignment = get_object_or_404(
        InternshipAssignment.objects.select_related('student', 'unit'),
        pk=assignment_pk,
    )

    if change_type not in dict(CHANGE_TYPE_CHOICES):
        raise PermissionDenied

    # Gleicher Typ darf nicht doppelt offen sein.
    open_same_type = assignment.change_requests.filter(
        change_type=change_type, status=CHANGE_REQUEST_STATUS_PENDING,
    ).first()
    if open_same_type:
        messages.warning(request, 'Für diesen Einsatz besteht bereits ein offener Antrag dieses Typs.')
        return redirect('instructor:chief_instructor_assignment_edit',
                        chief_public_id=chief_public_id, assignment_pk=assignment_pk)

    form_class = get_form_class(change_type)
    if form_class is None:
        raise PermissionDenied

    form_kwargs = {'assignment': assignment}
    if change_type == 'unit_change':
        from organisation.models import OrganisationalUnit
        descendant_pks, _, _ = _get_coordination_area(coordination)
        form_kwargs['unit_queryset'] = OrganisationalUnit.objects.filter(
            pk__in=descendant_pks, is_active=True,
        )
    elif change_type == 'location':
        from organisation.models import Location
        descendant_pks, _, _ = _get_coordination_area(coordination)
        form_kwargs['location_queryset'] = Location.objects.filter(
            units__pk__in=descendant_pks,
        ).distinct()

    form = form_class(request.POST or None, **form_kwargs)
    if request.method == 'POST' and form.is_valid():
        from django.utils import timezone
        from django.db import transaction

        cr = AssignmentChangeRequest(
            assignment=assignment,
            change_type=change_type,
            payload=form.get_payload(),
            reason=form.cleaned_data.get('reason', ''),
            requested_by=request.user,
        )

        if change_type == CHANGE_TYPE_INSTRUCTOR:
            # Praxistutor-Wechsel ohne Genehmigung: direkt anwenden + als approved speichern.
            try:
                with transaction.atomic():
                    cr.status = CHANGE_REQUEST_STATUS_APPROVED
                    cr.decided_by = request.user
                    cr.decided_at = timezone.now()
                    cr.save()
                    apply_change_request(cr, decided_by=request.user)
            except ValidationError as exc:
                messages.error(request, '; '.join(_flatten_validation_error(exc)))
                return redirect('instructor:chief_instructor_assignment_edit',
                                chief_public_id=chief_public_id, assignment_pk=assignment_pk)

            assignment.refresh_from_db()
            if assignment.instructor_id:
                from services.notifications import notify_instructor_of_assignment
                notify_instructor_of_assignment(request, assignment)
            messages.success(request, 'Praxistutor wurde aktualisiert.')
            return redirect('instructor:chief_instructor_assignment_edit',
                            chief_public_id=chief_public_id, assignment_pk=assignment_pk)

        cr.save()
        from services.notifications import notify_change_request_submitted
        notify_change_request_submitted(request, cr)
        messages.success(
            request,
            'Änderungsantrag wurde gestellt und wartet auf Bestätigung durch die Ausbildungsleitung.',
        )
        return redirect('instructor:chief_instructor_assignment_edit',
                        chief_public_id=chief_public_id, assignment_pk=assignment_pk)

    return render(request, 'instructor/change_request_form.html', {
        'chief': coordination,
        'assignment': assignment,
        'form': form,
        'change_type': change_type,
        'change_type_label': dict(CHANGE_TYPE_CHOICES)[change_type],
    })


def _flatten_validation_error(exc):
    """Macht aus einem Django ValidationError eine Liste lesbarer Strings."""
    if hasattr(exc, 'message_dict'):
        out = []
        for field, errs in exc.message_dict.items():
            for err in errs:
                out.append(f'{field}: {err}' if field != '__all__' else err)
        return out
    if hasattr(exc, 'messages'):
        return list(exc.messages)
    return [str(exc)]


def _require_training_director(user):
    from django.core.exceptions import PermissionDenied
    from services.roles import is_training_director
    if not (is_training_director(user) or user.is_staff):
        raise PermissionDenied


@login_required
def change_request_list(request):
    """Übersicht offener Änderungsanträge für die Ausbildungsleitung."""
    _require_training_director(request.user)
    from course.models import AssignmentChangeRequest, CHANGE_REQUEST_STATUS_PENDING

    pending = (
        AssignmentChangeRequest.objects
        .filter(status=CHANGE_REQUEST_STATUS_PENDING)
        .select_related(
            'assignment__student', 'assignment__unit',
            'assignment__schedule_block', 'requested_by',
        )
        .order_by('change_type', 'requested_at')
    )
    return render(request, 'instructor/change_request_list.html', {
        'change_requests': pending,
    })


@login_required
def change_request_review(request, change_request_public_id):
    """Ausbildungsleitung sieht einen einzelnen Änderungsantrag."""
    _require_training_director(request.user)
    from course.models import AssignmentChangeRequest

    cr = get_object_or_404(
        AssignmentChangeRequest.objects.select_related(
            'assignment__student', 'assignment__unit',
            'assignment__schedule_block', 'assignment__instructor',
            'assignment__location', 'requested_by',
        ),
        public_id=change_request_public_id,
    )
    payload_unit = payload_location = payload_instructor = None
    if cr.change_type == 'unit_change' and cr.payload.get('new_unit_id'):
        from organisation.models import OrganisationalUnit
        payload_unit = OrganisationalUnit.objects.filter(pk=cr.payload['new_unit_id']).first()
    if cr.change_type == 'location' and cr.payload.get('new_location_id'):
        from organisation.models import Location
        payload_location = Location.objects.filter(pk=cr.payload['new_location_id']).first()
    if cr.change_type == 'instructor' and cr.payload.get('new_instructor_id'):
        from instructor.models import Instructor
        payload_instructor = Instructor.objects.filter(pk=cr.payload['new_instructor_id']).first()

    return render(request, 'instructor/change_request_review.html', {
        'cr': cr,
        'payload_unit': payload_unit,
        'payload_location': payload_location,
        'payload_instructor': payload_instructor,
    })


@login_required
@require_POST
def change_request_approve(request, change_request_public_id):
    """Ausbildungsleitung genehmigt einen Änderungsantrag und führt ihn aus."""
    _require_training_director(request.user)
    from django.core.exceptions import ValidationError
    from django.utils import timezone
    from django.db import transaction
    from course.models import (
        AssignmentChangeRequest, CHANGE_REQUEST_STATUS_PENDING,
        CHANGE_REQUEST_STATUS_APPROVED,
    )
    from course.change_handlers import apply_change_request

    cr = get_object_or_404(
        AssignmentChangeRequest, public_id=change_request_public_id, status=CHANGE_REQUEST_STATUS_PENDING,
    )
    student_id = cr.assignment.student_id

    try:
        with transaction.atomic():
            cr.status = CHANGE_REQUEST_STATUS_APPROVED
            cr.decided_by = request.user
            cr.decided_at = timezone.now()
            cr.save(update_fields=['status', 'decided_by', 'decided_at'])
            apply_change_request(cr, decided_by=request.user)
    except ValidationError as exc:
        messages.error(request, 'Änderung konnte nicht angewendet werden: ' + '; '.join(_flatten_validation_error(exc)))
        return redirect('instructor:change_request_review', change_request_public_id=cr.public_id)

    from services.notifications import notify_change_request_decided
    notify_change_request_decided(request, cr)
    messages.success(request, f'Änderungsantrag wurde genehmigt: {cr.summary()}.')
    return redirect('student:student_detail', pk=student_id)


@login_required
@require_POST
def change_request_reject(request, change_request_public_id):
    """Ausbildungsleitung lehnt einen Änderungsantrag ab."""
    _require_training_director(request.user)
    from django.utils import timezone
    from course.models import (
        AssignmentChangeRequest, CHANGE_REQUEST_STATUS_PENDING,
        CHANGE_REQUEST_STATUS_REJECTED,
    )

    cr = get_object_or_404(
        AssignmentChangeRequest, public_id=change_request_public_id, status=CHANGE_REQUEST_STATUS_PENDING,
    )
    cr.status = CHANGE_REQUEST_STATUS_REJECTED
    cr.decided_by = request.user
    cr.decided_at = timezone.now()
    cr.rejection_reason = request.POST.get('rejection_reason', '').strip()
    cr.save(update_fields=['status', 'decided_by', 'decided_at', 'rejection_reason'])

    from services.notifications import notify_change_request_decided
    notify_change_request_decided(request, cr)
    messages.info(request, f'Änderungsantrag wurde abgelehnt: {cr.summary()}.')
    return redirect('student:student_detail', pk=cr.assignment.student_id)


# ── AJAX ──────────────────────────────────────────────────────────────────────

@login_required
def locations_for_unit(request):
    """AJAX: Gibt verfügbare Standorte für eine Organisationseinheit zurück."""
    from organisation.models import OrganisationalUnit
    unit_pk = request.GET.get('unit')
    if not unit_pk:
        return JsonResponse({'locations': []})
    unit = OrganisationalUnit.objects.filter(pk=unit_pk).first()
    if not unit:
        return JsonResponse({'locations': []})
    locations = [
        {'id': loc.pk, 'name': str(loc)}
        for loc in unit.get_all_locations().select_related('address')
    ]
    return JsonResponse({'locations': locations})

@login_required
def instructors_for_unit(request):
    """AJAX: Gibt bestätigte Praxistutoren für eine Organisationseinheit zurück.

    Der aktuell zugewiesene Praxistutor (``current``) wird immer in der Liste
    enthalten, auch wenn er die Filter nicht mehr erfüllt – andernfalls würde
    das Frontend ihn stillschweigend aus dem Formular entfernen.
    """
    from course.models import InternshipAssignment
    from django.db.models import Count, Q

    unit_pk = request.GET.get('unit')
    job_profile_pk = request.GET.get('job_profile')
    location_pk = request.GET.get('location')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    exclude_pk = request.GET.get('exclude')
    current_instructor_pk = request.GET.get('current')

    if not unit_pk:
        return JsonResponse({'instructors': []})

    qs = Instructor.objects.filter(unit_id=unit_pk, status=Instructor.CONFIRMED).order_by('last_name', 'first_name')
    if job_profile_pk:
        qs = qs.filter(job_profiles=job_profile_pk)
    if location_pk:
        qs = qs.filter(location_id=location_pk)

    overlap_filter = Q()
    if start_date and end_date:
        overlap_filter = Q(
            internshipassignment__start_date__lte=end_date,
            internshipassignment__end_date__gte=start_date,
        )
        if exclude_pk:
            overlap_filter &= ~Q(internshipassignment__pk=exclude_pk)

    qs = qs.annotate(current_count=Count('internshipassignment', filter=overlap_filter))

    data = [
        {
            'pk': i.pk,
            'name': str(i),
            'current_count': i.current_count,
            'full': i.current_count >= 5,
        }
        for i in qs
    ]

    # Aktuellen Praxistutor immer einschliessen, auch wenn er Filter nicht mehr erfuellt
    if current_instructor_pk and not any(str(d['pk']) == str(current_instructor_pk) for d in data):
        current = Instructor.objects.filter(pk=current_instructor_pk).first()
        if current:
            data.append({
                'pk': current.pk,
                'name': str(current),
                'current_count': 0,
                'full': False,
            })

    return JsonResponse({'instructors': data})
