# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views der Raumbuchung – sowohl Verwaltungs- als auch Portal-Seite."""
from datetime import date as date_type, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    WorkspaceBookingForm,
    WorkspaceBookingPortalForm,
    WorkspaceClosureForm,
)
from .models import (
    STATUS_CONFIRMED,
    Workspace,
    WorkspaceBooking,
    WorkspaceClosure,
    WorkspaceType,
)


# ── Belegungsplan (Monatsansicht) ───────────────────────────────────────────

WEEKDAY_SHORT_DE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
MONTH_NAMES_DE = [
    '', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
]


@login_required
def workspace_calendar(request):
    """Monats-Belegungsplan aller Arbeitsplätze.

    Sichtbarkeit:
    - Ausbildungsleitung / -referat: voll mit Klarnamen, Klick auf Buchung führt zur Storno-Bestätigung
    - Ausbildungskoordination: nur „Belegt" / „Frei" (anonymisiert), keine Aktionen
    """
    from services.roles import (
        is_training_director, is_training_office, is_training_coordinator,
    )
    from services.colors import BUNDESFARBEN_PALETTE, BUNDESFARBEN_BY_NAME

    user = request.user
    can_view_full = (
        user.is_staff
        or is_training_director(user)
        or is_training_office(user)
    )
    can_view_anonymized = is_training_coordinator(user)
    if not (can_view_full or can_view_anonymized):
        raise PermissionDenied

    anonymize = (not can_view_full) and can_view_anonymized

    today = date_type.today()
    try:
        year  = int(request.GET.get('year',  today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month
    if not (1 <= month <= 12):
        month = today.month

    month_start = date_type(year, month, 1)
    if month == 12:
        next_month_start = date_type(year + 1, 1, 1)
    else:
        next_month_start = date_type(year, month + 1, 1)
    month_end = next_month_start - timedelta(days=1)
    month_days = (month_end - month_start).days + 1

    prev_month_dt = month_start - timedelta(days=1)
    prev_year, prev_month = prev_month_dt.year, prev_month_dt.month
    next_year, next_month = next_month_start.year, next_month_start.month

    # Tagesleiste (mit Wochenenden, heutiger Tag markiert)
    days_data = []
    for i in range(month_days):
        d = month_start + timedelta(days=i)
        days_data.append({
            'date':       d,
            'day':        d.day,
            'weekday':    WEEKDAY_SHORT_DE[d.weekday()],
            'is_weekend': d.weekday() >= 5,
            'is_today':   d == today,
            'offset':     f'{i / month_days * 100:.6f}',
            'width':      f'{1 / month_days * 100:.6f}',
        })

    today_offset = None
    if month_start <= today <= month_end:
        today_offset = f'{(today - month_start).days / month_days * 100:.4f}'

    from organisation.models import Location
    all_locations = Location.objects.order_by('name')
    selected_ids = request.GET.getlist('locations')
    if selected_ids:
        try:
            selected_ids = [int(i) for i in selected_ids]
        except ValueError:
            selected_ids = []

    workspaces_qs = (
        Workspace.objects
        .filter(is_active=True)
        .select_related('workspace_type', 'location')
        .order_by('location__name', 'workspace_type__name', 'name')
    )
    if selected_ids:
        workspaces_qs = workspaces_qs.filter(location_id__in=selected_ids)

    bar_height  = 32
    bar_gap     = 4
    row_padding = 4

    by_location: dict = {}
    for ws in workspaces_qs:
        items_data = []

        bookings = (
            ws.bookings
            .filter(status=STATUS_CONFIRMED, date__gte=month_start, date__lte=month_end)
            .select_related('student')
            .order_by('date')
        )
        for b in bookings:
            offset = (b.date - month_start).days / month_days * 100
            width  = 1 / month_days * 100
            items_data.append({
                'type':       'booking',
                'booking':    b,
                'offset':     f'{offset:.4f}',
                'width':      f'{width:.4f}',
                'raw_offset': offset,
                'raw_end':    offset + width,
                'label':      'Belegt' if anonymize else f'{b.student.first_name} {b.student.last_name}',
                'date_fmt':   b.date.strftime('%d.%m.%Y'),
            })

        for c in ws.closures.filter(start_date__lte=month_end, end_date__gte=month_start):
            clip_start = max(c.start_date, month_start)
            clip_end   = min(c.end_date,   month_end)
            offset = (clip_start - month_start).days / month_days * 100
            width  = ((clip_end - clip_start).days + 1) / month_days * 100
            items_data.append({
                'type':       'closure',
                'closure':    c,
                'offset':     f'{offset:.4f}',
                'width':      f'{width:.4f}',
                'raw_offset': offset,
                'raw_end':    offset + width,
                'label':      c.reason or 'Gesperrt',
                'start_fmt':  clip_start.strftime('%d.%m.%Y'),
                'end_fmt':    clip_end.strftime('%d.%m.%Y'),
            })

        # Spurzuordnung (Greedy-Intervallpackung)
        items_data.sort(key=lambda x: x['raw_offset'])
        lane_ends: list = []
        for item in items_data:
            placed = False
            for i, end in enumerate(lane_ends):
                if item['raw_offset'] >= end:
                    lane_ends[i] = item['raw_end']
                    item['lane'] = i
                    placed = True
                    break
            if not placed:
                item['lane'] = len(lane_ends)
                lane_ends.append(item['raw_end'])

        # Konfliktvermeidende Farben für Buchungen aus der Bundesfarben-Palette
        booking_items = [it for it in items_data if it['type'] == 'booking']
        for i, it in enumerate(booking_items):
            if anonymize:
                it['color'] = BUNDESFARBEN_BY_NAME['Dunkelgrau']
                continue
            used = {
                other['color_idx']
                for other in booking_items[:i]
                if it['raw_offset'] < other['raw_end'] and it['raw_end'] > other['raw_offset']
            }
            preferred = hash(str(it['booking'].student_id)) % len(BUNDESFARBEN_PALETTE)
            color_idx = preferred
            while color_idx in used:
                color_idx = (color_idx + 1) % len(BUNDESFARBEN_PALETTE)
            it['color_idx'] = color_idx
            it['color'] = BUNDESFARBEN_PALETTE[color_idx]

        # Bei Kapazität > 1 mindestens so viele Lanes wie Kapazität anzeigen
        num_lanes = max(len(lane_ends), ws.capacity, 1)
        row_height = bar_gap + num_lanes * (bar_height + bar_gap) + row_padding

        for item in items_data:
            item['top_px'] = bar_gap + item['lane'] * (bar_height + bar_gap)

        by_location.setdefault(ws.location_id, {
            'location': ws.location,
            'workspaces': [],
        })['workspaces'].append({
            'workspace':  ws,
            'items':      items_data,
            'row_height': row_height,
        })

    calendar_data = list(by_location.values())

    return render(request, 'workspace/workspace_calendar.html', {
        'year':              year,
        'month':             month,
        'month_label':       f'{MONTH_NAMES_DE[month]} {year}',
        'prev_year':         prev_year,
        'prev_month':        prev_month,
        'next_year':         next_year,
        'next_month':        next_month,
        'today_year':        today.year,
        'today_month':       today.month,
        'days_data':         days_data,
        'today_offset':      today_offset,
        'calendar_data':     calendar_data,
        'all_locations':     all_locations,
        'selected_loc_ids':  selected_ids,
        'anonymize':         anonymize,
        'can_view_full':     can_view_full,
        'color_chrome':      BUNDESFARBEN_BY_NAME['Blau'],
        'color_chrome_dark': BUNDESFARBEN_BY_NAME['Petrol'],
        'color_today':       BUNDESFARBEN_BY_NAME['Rot'],
        'color_legend_occupied': BUNDESFARBEN_BY_NAME['Blau'],
    })


# ── Admin / Koordinationen ──────────────────────────────────────────────────

@login_required
def workspace_list(request):
    """Übersicht aller Arbeitsplätze mit Filter nach Standort und Typ."""
    qs = (
        Workspace.objects.filter(is_active=True)
        .select_related('workspace_type', 'location')
    )
    location_pk = request.GET.get('location')
    type_pk     = request.GET.get('type')
    if location_pk:
        qs = qs.filter(location_id=location_pk)
    if type_pk:
        qs = qs.filter(workspace_type_id=type_pk)

    today = date_type.today()
    rows = []
    for ws in qs:
        rows.append({
            'workspace': ws,
            'today_remaining': ws.remaining_capacity_on(today),
            'today_blocked':   ws.is_blocked_on(today),
        })

    from organisation.models import Location
    return render(request, 'workspace/workspace_list.html', {
        'rows': rows,
        'today': today,
        'locations': Location.objects.order_by('name'),
        'types': WorkspaceType.objects.filter(is_active=True).order_by('name'),
        'filter_location': int(location_pk) if location_pk else None,
        'filter_type': int(type_pk) if type_pk else None,
    })


@login_required
def workspace_detail(request, public_id):
    """Detailseite eines Arbeitsplatzes mit 4-Wochen-Belegungskalender."""
    workspace = get_object_or_404(
        Workspace.objects.select_related('workspace_type', 'location', 'unit'),
        public_id=public_id,
    )

    horizon_days = max(workspace.booking_horizon_days, 7)
    start = date_type.today()
    end   = start + timedelta(days=horizon_days - 1)

    bookings = (
        workspace.bookings
        .filter(status=STATUS_CONFIRMED, date__gte=start, date__lte=end)
        .select_related('student', 'booked_by')
    )
    closures = workspace.closures.filter(end_date__gte=start, start_date__lte=end)

    by_date = {}
    for b in bookings:
        by_date.setdefault(b.date, []).append(b)

    closed_dates = set()
    for c in closures:
        d = max(c.start_date, start)
        last = min(c.end_date, end)
        while d <= last:
            closed_dates.add(d)
            d += timedelta(days=1)

    days = []
    d = start
    while d <= end:
        day_bookings = by_date.get(d, [])
        days.append({
            'date': d,
            'bookings': day_bookings,
            'is_closed': d in closed_dates,
            'remaining': 0 if d in closed_dates else max(0, workspace.capacity - len(day_bookings)),
        })
        d += timedelta(days=1)

    return render(request, 'workspace/workspace_detail.html', {
        'workspace': workspace,
        'days': days,
        'closures': closures,
    })


@login_required
def booking_list(request):
    """Liste aller Buchungen mit Filter (Status, Standort, Datum)."""
    qs = (
        WorkspaceBooking.objects
        .select_related('workspace__location', 'workspace__workspace_type', 'student', 'booked_by')
    )
    status = request.GET.get('status', STATUS_CONFIRMED)
    location_pk = request.GET.get('location')
    if status in {'confirmed', 'cancelled', 'all'}:
        if status != 'all':
            qs = qs.filter(status=status)
    if location_pk:
        qs = qs.filter(workspace__location_id=location_pk)

    qs = qs.order_by('-date', 'workspace__name')[:500]

    from organisation.models import Location
    return render(request, 'workspace/booking_list.html', {
        'bookings': qs,
        'status': status,
        'locations': Location.objects.order_by('name'),
        'filter_location': int(location_pk) if location_pk else None,
    })


@login_required
def booking_create(request, workspace_public_id=None):
    """Neue Buchung anlegen (Admin/Koordination)."""
    initial_workspace = None
    if workspace_public_id:
        initial_workspace = get_object_or_404(Workspace, pk=workspace_public_id)

    if request.method == 'POST':
        form = WorkspaceBookingForm(request.POST, initial_workspace=initial_workspace)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            try:
                booking.full_clean()
            except ValidationError as e:
                for field, errs in e.message_dict.items():
                    for err in errs:
                        form.add_error(field if field != '__all__' else None, err)
            else:
                booking.save()
                _notify_booking_confirmed(request, booking)
                messages.success(
                    request,
                    f'Buchung für {booking.student} am '
                    f'{booking.date.strftime("%d.%m.%Y")} wurde angelegt.',
                )
                return redirect('workspace:workspace_detail', pk=booking.workspace_id)
    else:
        date_str = request.GET.get('date')
        initial = {}
        if date_str:
            try:
                initial['date'] = date_type.fromisoformat(date_str)
            except ValueError:
                pass
        form = WorkspaceBookingForm(initial=initial, initial_workspace=initial_workspace)

    return render(request, 'workspace/booking_form.html', {
        'form': form,
        'workspace': initial_workspace,
        'cancel_url': (
            reverse('workspace:workspace_detail', kwargs={'public_id': initial_workspace.public_id})
            if initial_workspace else reverse('workspace:workspace_list')
        ),
    })


@login_required
def booking_cancel(request, public_id):
    """Buchung stornieren (von Buchender selbst oder Admin/Koordination)."""
    booking = get_object_or_404(
        WorkspaceBooking.objects.select_related('workspace', 'student'),
        public_id=public_id,
    )

    if booking.status != STATUS_CONFIRMED:
        messages.warning(request, 'Diese Buchung ist bereits storniert.')
        return redirect('workspace:workspace_detail', public_id=booking.workspace_id)

    if request.method == 'POST':
        booking.cancel(user=request.user)
        _notify_booking_cancelled(request, booking)
        messages.success(
            request,
            f'Buchung für {booking.student} am '
            f'{booking.date.strftime("%d.%m.%Y")} wurde storniert.',
        )
        return redirect('workspace:workspace_detail', public_id=booking.workspace_id)

    return render(request, 'workspace/booking_cancel_confirm.html', {
        'booking': booking,
    })


@login_required
def closure_create(request, workspace_public_id=None):
    """Sperrzeitraum für einen Arbeitsplatz anlegen."""
    initial_workspace = None
    if workspace_public_id:
        initial_workspace = get_object_or_404(Workspace, pk=workspace_public_id)

    if request.method == 'POST':
        form = WorkspaceClosureForm(request.POST)
        if form.is_valid():
            closure = form.save()
            messages.success(request, f'Sperrzeitraum für {closure.workspace} wurde angelegt.')
            return redirect('workspace:workspace_detail', pk=closure.workspace_id)
    else:
        initial = {'workspace': initial_workspace.pk} if initial_workspace else {}
        form = WorkspaceClosureForm(initial=initial)

    return render(request, 'workspace/closure_form.html', {
        'form': form,
        'workspace': initial_workspace,
    })


@login_required
def closure_delete(request, public_id):
    """Sperrzeitraum entfernen."""
    closure = get_object_or_404(WorkspaceClosure, public_id=public_id)
    workspace_id = closure.workspace_id
    if request.method == 'POST':
        closure.delete()
        messages.success(request, 'Sperrzeitraum wurde entfernt.')
        return redirect('workspace:workspace_detail', public_id=workspace_id)
    return render(request, 'workspace/closure_delete_confirm.html', {
        'closure': closure,
    })


# ── Portal (Nachwuchskräfte) ────────────────────────────────────────────────

def _get_student_or_403(request):
    """Gibt das Nachwuchskraft-Profil des eingeloggten Nutzers zurück oder wirft 403."""
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        raise PermissionDenied
    return student


@login_required
def portal_my_bookings(request):
    """Eigene Buchungen der Nachwuchskraft (kommende und vergangene)."""
    student = _get_student_or_403(request)
    today = date_type.today()

    upcoming = (
        WorkspaceBooking.objects
        .filter(student=student, status=STATUS_CONFIRMED, date__gte=today)
        .select_related('workspace__location', 'workspace__workspace_type')
        .order_by('date')
    )
    past = (
        WorkspaceBooking.objects
        .filter(student=student, date__lt=today)
        .select_related('workspace__location', 'workspace__workspace_type')
        .order_by('-date')[:30]
    )
    return render(request, 'workspace/portal_my_bookings.html', {
        'student': student,
        'upcoming': upcoming,
        'past': past,
        'today': today,
    })


@login_required
def portal_workspace_list(request):
    """Alle buchbaren Arbeitsplätze (alle Standorte sichtbar – Desk-Sharing erwünscht)."""
    student = _get_student_or_403(request)
    qs = (
        Workspace.objects.filter(is_active=True)
        .select_related('workspace_type', 'location')
        .order_by('location__name', 'workspace_type__name', 'name')
    )

    today = date_type.today()
    rows = []
    for ws in qs:
        rows.append({
            'workspace': ws,
            'today_remaining': ws.remaining_capacity_on(today),
            'today_blocked':   ws.is_blocked_on(today),
        })

    return render(request, 'workspace/portal_workspace_list.html', {
        'student': student,
        'rows': rows,
        'today': today,
    })


@login_required
def portal_workspace_detail(request, public_id):
    """Belegungs-Übersicht eines Arbeitsplatzes für Nachwuchskräfte."""
    student = _get_student_or_403(request)
    workspace = get_object_or_404(Workspace.objects.select_related('location', 'workspace_type'), public_id=public_id)

    horizon_days = max(workspace.booking_horizon_days, 7)
    start = date_type.today()
    end   = start + timedelta(days=horizon_days - 1)

    bookings = (
        workspace.bookings
        .filter(status=STATUS_CONFIRMED, date__gte=start, date__lte=end)
    )
    closures = workspace.closures.filter(end_date__gte=start, start_date__lte=end)
    own_dates = set(
        WorkspaceBooking.objects
        .filter(student=student, status=STATUS_CONFIRMED, date__gte=start, date__lte=end)
        .values_list('date', flat=True)
    )

    used_by_date = {}
    for b in bookings:
        used_by_date[b.date] = used_by_date.get(b.date, 0) + 1

    closed_dates = set()
    for c in closures:
        d = max(c.start_date, start)
        last = min(c.end_date, end)
        while d <= last:
            closed_dates.add(d)
            d += timedelta(days=1)

    days = []
    d = start
    while d <= end:
        used = used_by_date.get(d, 0)
        days.append({
            'date': d,
            'is_closed': d in closed_dates,
            'remaining': 0 if d in closed_dates else max(0, workspace.capacity - used),
            'is_own': d in own_dates,
        })
        d += timedelta(days=1)

    return render(request, 'workspace/portal_workspace_detail.html', {
        'student': student,
        'workspace': workspace,
        'days': days,
    })


@login_required
def portal_booking_create(request, workspace_public_id=None):
    """Nachwuchskraft bucht einen Arbeitsplatz für sich selbst."""
    student = _get_student_or_403(request)
    initial_workspace = None
    if workspace_public_id:
        initial_workspace = get_object_or_404(Workspace, pk=workspace_public_id, is_active=True)

    if request.method == 'POST':
        form = WorkspaceBookingPortalForm(request.POST, initial_workspace=initial_workspace)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.student = student
            booking.booked_by = request.user
            booking.status = STATUS_CONFIRMED
            try:
                booking.full_clean()
            except ValidationError as e:
                for field, errs in e.message_dict.items():
                    for err in errs:
                        form.add_error(field if field != '__all__' else None, err)
            else:
                booking.save()
                _notify_booking_confirmed(request, booking)
                _maybe_warn_about_assignment_conflict(request, booking)
                messages.success(
                    request,
                    f'Buchung für {booking.workspace.name} am '
                    f'{booking.date.strftime("%d.%m.%Y")} wurde angelegt.',
                )
                return redirect('workspace:portal_my_bookings')
    else:
        date_str = request.GET.get('date')
        initial = {}
        if date_str:
            try:
                initial['date'] = date_type.fromisoformat(date_str)
            except ValueError:
                pass
        form = WorkspaceBookingPortalForm(initial=initial, initial_workspace=initial_workspace)

    return render(request, 'workspace/portal_booking_form.html', {
        'student': student,
        'form': form,
        'workspace': initial_workspace,
    })


@login_required
def portal_booking_cancel(request, public_id):
    """Nachwuchskraft storniert eine eigene Buchung."""
    student = _get_student_or_403(request)
    booking = get_object_or_404(
        WorkspaceBooking.objects.select_related('workspace'),
        public_id=public_id,
        student=student,
    )

    if booking.status != STATUS_CONFIRMED:
        messages.warning(request, 'Diese Buchung ist bereits storniert.')
        return redirect('workspace:portal_my_bookings')

    if request.method == 'POST':
        booking.cancel(user=request.user)
        _notify_booking_cancelled(request, booking)
        messages.success(
            request,
            f'Buchung für {booking.workspace.name} am '
            f'{booking.date.strftime("%d.%m.%Y")} wurde storniert.',
        )
        return redirect('workspace:portal_my_bookings')

    return render(request, 'workspace/portal_booking_cancel.html', {
        'student': student,
        'booking': booking,
    })


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _notify_booking_confirmed(request, booking):
    """Versendet die Bestätigungs-Mail mit iCal-Anhang (REQUEST)."""
    from services.notifications import notify_workspace_booking_confirmed
    try:
        notify_workspace_booking_confirmed(request, booking)
    except Exception:
        # Buchung darf nicht an Mail-Problemen scheitern
        pass


def _notify_booking_cancelled(request, booking):
    """Versendet die Stornierungs-Mail mit iCal-Anhang (CANCEL)."""
    from services.notifications import notify_workspace_booking_cancelled
    try:
        notify_workspace_booking_cancelled(request, booking)
    except Exception:
        pass


def _maybe_warn_about_assignment_conflict(request, booking):
    """Warnt freundlich, wenn die Nachwuchskraft an dem Tag eigentlich an einer Station ist.

    Bewusst nur Hinweis, kein Abbruch – Desk-Sharing während Dienstreise und
    Lerntag-Kombinationen sind absichtlich zulässig.
    """
    try:
        from course.models import InternshipAssignment, ASSIGNMENT_STATUS_APPROVED
        a = (
            InternshipAssignment.objects
            .filter(
                student=booking.student,
                status=ASSIGNMENT_STATUS_APPROVED,
                start_date__lte=booking.date,
                end_date__gte=booking.date,
            )
            .select_related('unit', 'location')
            .first()
        )
        if a and a.location_id and a.location_id != booking.workspace.location_id:
            messages.info(
                request,
                f'Hinweis: Du bist am {booking.date.strftime("%d.%m.%Y")} laut Stationsplan '
                f'in {a.unit.name} eingesetzt – die gebuchte Lerninsel/Büro liegt an einem '
                f'anderen Standort ({booking.workspace.location.name}).',
            )
    except Exception:
        pass