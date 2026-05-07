# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für die Wohnheimverwaltung (Belegung, Sperrung, Belegungskalender, Reservierungsbestätigung)."""
from datetime import date, timedelta
from io import BytesIO

import requests as http_requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Dormitory, Room, RoomAssignment, RoomBlock, ReservationTemplate
from .forms import RoomAssignmentForm, RoomBlockForm
from services.paperless import PaperlessService

# Farbpalette für die Belegungsbalken im Kalender (Stilguide Bundesregierung)
from services.colors import BUNDESFARBEN_PALETTE as ASSIGNMENT_COLORS  # noqa: E402

@login_required
def dormitory_list(request):
    """Listenansicht aller Wohnheime."""
    dormitories = Dormitory.objects.prefetch_related("rooms").all()
    return render(request, "dormitory/dormitory_list.html", {"dormitories": dormitories})


@login_required
def dormitory_detail(request, public_id):
    """Detailansicht eines Wohnheims mit allen Zimmern."""
    dormitory = get_object_or_404(Dormitory, public_id=public_id)
    rooms = dormitory.rooms.prefetch_related("assignments__student").all()
    return render(request, "dormitory/dormitory_detail.html", {
        "dormitory": dormitory,
        "rooms": rooms,
    })


@login_required
def room_detail(request, public_id):
    """Detailansicht eines Zimmers mit Belegungen und Sperrungen."""
    room = get_object_or_404(Room, public_id=public_id)
    assignments = room.assignments.select_related("student").order_by("-start_date")
    blocks = room.blocks.order_by("-start_date")
    return render(request, "dormitory/room_detail.html", {
        "room": room,
        "assignments": assignments,
        "blocks": blocks,
    })


@login_required
def assignment_create(request, room_public_id=None):
    """Neue Zimmerbelegung anlegen."""
    initial = {}
    if room_public_id:
        room = get_object_or_404(Room, public_id=room_public_id)
        initial["room"] = room
    for key in ("start_date", "end_date", "room"):
        if key in request.GET and key not in initial:
            initial[key] = request.GET[key]
    form = RoomAssignmentForm(request.POST or None, initial=initial)
    if form.is_valid():
        try:
            assignment = form.save(commit=False)
            assignment.full_clean()
            assignment.save()
            messages.success(request, "Belegung wurde gespeichert.")
            return redirect("dormitory:room_detail", public_id=assignment.room.public_id)
        except Exception as e:
            form.add_error(None, str(e))
    return render(request, "dormitory/assignment_form.html", {"form": form, "action": "Create"})


@login_required
def assignment_edit(request, public_id):
    """Bestehende Zimmerbelegung bearbeiten."""
    assignment = get_object_or_404(RoomAssignment, public_id=public_id)
    form = RoomAssignmentForm(request.POST or None, instance=assignment)
    if form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.full_clean()
            obj.save()
            messages.success(request, "Belegung wurde aktualisiert.")
            return redirect("dormitory:room_detail", public_id=obj.room.public_id)
        except Exception as e:
            form.add_error(None, str(e))
    return render(request, "dormitory/assignment_form.html", {"form": form, "action": "Edit", "assignment": assignment})


@login_required
def block_create(request, room_public_id=None):
    """Neue Zimmersperrung anlegen."""
    initial = {}
    if room_public_id:
        room = get_object_or_404(Room, public_id=room_public_id)
        initial["room"] = room
    for key in ("start_date", "end_date", "room"):
        if key in request.GET and key not in initial:
            initial[key] = request.GET[key]
    form = RoomBlockForm(request.POST or None, initial=initial)
    if form.is_valid():
        try:
            block = form.save(commit=False)
            block.full_clean()
            block.save()
            messages.success(request, "Sperrung wurde gespeichert.")
            return redirect("dormitory:room_detail", public_id=block.room.public_id)
        except Exception as e:
            form.add_error(None, str(e))
    return render(request, "dormitory/block_form.html", {"form": form, "action": "Neue"})


@login_required
def block_edit(request, public_id):
    """Bestehende Zimmersperrung bearbeiten."""
    block = get_object_or_404(RoomBlock, public_id=public_id)
    form = RoomBlockForm(request.POST or None, instance=block)
    if form.is_valid():
        try:
            obj = form.save(commit=False)
            obj.full_clean()
            obj.save()
            messages.success(request, "Sperrung aktualisiert.")
            return redirect("dormitory:room_detail", public_id=obj.room.public_id)
        except Exception as e:
            form.add_error(None, str(e))
    return render(request, "dormitory/block_form.html", {"form": form, "action": "Bearbeite", "room_block": block})


@login_required
def block_delete(request, public_id):
    """Zimmersperrung loeschen (mit Bestaetigungsseite)."""
    block = get_object_or_404(RoomBlock, public_id=public_id)
    if request.method == "POST":
        room_pk = block.room.public_id
        block.delete()
        messages.success(request, "Sperrung wurde gelöscht.")
        return redirect("dormitory:room_detail", public_id=room_pk)
    return render(request, "dormitory/block_confirm_delete.html", {"room_block": block})


@login_required
def occupancy_calendar(request):
    """Jahres-Belegungskalender mit Balkenansicht pro Zimmer."""
    year = int(request.GET.get("year", date.today().year))
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    year_days = (year_end - year_start).days + 1

    # Monatskopfzeilen (Offset + Breite als % des Jahres)
    months_data = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end = date(year, m + 1, 1) - timedelta(days=1) if m < 12 else year_end
        m_days = (m_end - m_start).days + 1
        months_data.append({
            "name": m_start.strftime("%B"),
            "short": m_start.strftime("%b"),
            "days": m_days,
            "offset": f"{(m_start - year_start).days / year_days * 100:.6f}",
            "width": f"{m_days / year_days * 100:.6f}",
        })

    # Markierung für den heutigen Tag
    today = date.today()
    today_offset = None
    if year_start <= today <= year_end:
        today_offset = f"{(today - year_start).days / year_days * 100:.4f}"

    from services.roles import is_dormitory_management, get_dormitory_management_profile
    if is_dormitory_management(request.user):
        hv_profile = get_dormitory_management_profile(request.user)
        if hv_profile:
            all_dormitories = Dormitory.objects.filter(pk=hv_profile.dormitory_id).order_by("name")
            selected_ids = [hv_profile.dormitory_id]
            dormitories = all_dormitories.prefetch_related("rooms")
        else:
            all_dormitories = Dormitory.objects.none()
            selected_ids = []
            dormitories = all_dormitories
    else:
        all_dormitories = Dormitory.objects.order_by("name")
        selected_ids = request.GET.getlist("dorms")
        if selected_ids:
            try:
                selected_ids = [int(i) for i in selected_ids]
            except ValueError:
                selected_ids = []
        dormitories = (
            all_dormitories.filter(pk__in=selected_ids).prefetch_related("rooms")
            if selected_ids
            else all_dormitories.prefetch_related("rooms")
        )
    calendar_data = []

    bar_height = 38   # px per bar
    bar_gap    = 6    # px above first bar and between lanes
    row_padding = 6   # px below last bar

    for dorm in dormitories:
        rooms_data = []
        for room in dorm.rooms.order_by("number"):
            items_data = []

            # Belegungen
            qs = room.assignments.select_related("student").filter(
                start_date__lte=year_end
            ).filter(
                q_active_or_ending_after(year_start)
            ).order_by("start_date")
            for a in qs:
                clip_start = max(a.start_date, year_start)
                clip_end = min(a.end_date or year_end, year_end)
                if clip_start > clip_end:
                    continue
                raw_offset = (clip_start - year_start).days / year_days * 100
                raw_width = max(((clip_end - clip_start).days + 1) / year_days * 100, 0.3)
                items_data.append({
                    "type": "assignment",
                    "assignment": a,
                    "offset": f"{raw_offset:.4f}",
                    "width": f"{raw_width:.4f}",
                    "raw_offset": raw_offset,
                    "raw_end": raw_offset + raw_width,
                    "label": f"{a.student.first_name} {a.student.last_name}",
                    "start_fmt": a.start_date.strftime("%d.%m.%Y"),
                    "end_fmt": a.end_date.strftime("%d.%m.%Y") if a.end_date else "open",
                })

            # Sperrungen
            for b in room.blocks.filter(start_date__lte=year_end, end_date__gte=year_start).order_by("start_date"):
                clip_start = max(b.start_date, year_start)
                clip_end = min(b.end_date, year_end)
                if clip_start > clip_end:
                    continue
                raw_offset = (clip_start - year_start).days / year_days * 100
                raw_width = max(((clip_end - clip_start).days + 1) / year_days * 100, 0.3)
                items_data.append({
                    "type": "block",
                    "block": b,
                    "offset": f"{raw_offset:.4f}",
                    "width": f"{raw_width:.4f}",
                    "raw_offset": raw_offset,
                    "raw_end": raw_offset + raw_width,
                    "label": b.reason or "Gesperrt",
                    "start_fmt": b.start_date.strftime("%d.%m.%Y"),
                    "end_fmt": b.end_date.strftime("%d.%m.%Y"),
                })

            # Nach Startdatum sortieren für korrekte Spurzuordnung
            items_data.sort(key=lambda x: x["raw_offset"])

            # Jeden Balken der niedrigsten freien Spur zuordnen (Greedy-Intervallpackung)
            lane_ends = []
            for item in items_data:
                placed = False
                for i, end in enumerate(lane_ends):
                    if item["raw_offset"] >= end:
                        lane_ends[i] = item["raw_end"]
                        item["lane"] = i
                        placed = True
                        break
                if not placed:
                    item["lane"] = len(lane_ends)
                    lane_ends.append(item["raw_end"])

            # Konfliktvermeidende Farbzuweisung für Belegungen
            assignment_items = [it for it in items_data if it["type"] == "assignment"]
            for i, a_data in enumerate(assignment_items):
                used_colors = {
                    other["color_idx"]
                    for other in assignment_items[:i]
                    if a_data["raw_offset"] < other["raw_end"]
                    and a_data["raw_end"] > other["raw_offset"]
                }
                preferred = hash(str(a_data["assignment"].student_id)) % len(ASSIGNMENT_COLORS)
                color_idx = preferred
                while color_idx in used_colors:
                    color_idx = (color_idx + 1) % len(ASSIGNMENT_COLORS)
                a_data["color_idx"] = color_idx
                a_data["color"] = ASSIGNMENT_COLORS[color_idx]

            num_lanes = max(len(lane_ends), 1)
            row_height = bar_gap + num_lanes * (bar_height + bar_gap) + row_padding

            # Vertikale Pixelposition pro Balken berechnen
            for item in items_data:
                item["top_px"] = bar_gap + item["lane"] * (bar_height + bar_gap)

            rooms_data.append({
                "room": room,
                "assignments": items_data,
                "row_height": row_height,
            })
        calendar_data.append({"dormitory": dorm, "rooms": rooms_data})

    from services.colors import BUNDESFARBEN_BY_NAME as _BF
    return render(request, "dormitory/occupancy_calendar.html", {
        "year": year,
        "prev_year": year - 1,
        "next_year": year + 1,
        "year_start_iso": year_start.isoformat(),
        "year_days": year_days,
        "months_data": months_data,
        "today_offset": today_offset,
        "calendar_data": calendar_data,
        "all_dormitories": all_dormitories,
        "selected_dorm_ids": selected_ids,
        "color_chrome": _BF['Blau'],
        "color_chrome_dark": _BF['Petrol'],
        "color_today": _BF['Rot'],
        "color_legend_occupied": _BF['Blau'],
    })


@login_required
def confirmation_loading(request, public_id):
    """Reservierungsbestätigung: sofort zur Vorschau oder Ladeanzeige."""
    assignment = get_object_or_404(RoomAssignment, public_id=public_id)
    if assignment.paperless_confirmation_id:
        return redirect("document:document_preview", paperless_id=assignment.paperless_confirmation_id)
    return render(request, "dormitory/confirmation_loading.html", {"assignment": assignment})


@login_required
@require_POST
def confirmation_generate(request, public_id):
    """Generiert die Reservierungsbestätigung (DOCX) und lädt sie in Paperless hoch; gibt JSON zurück."""
    assignment = get_object_or_404(
        RoomAssignment.objects.select_related("student", "room__dormitory"),
        public_id=public_id,
    )

    dormitory = assignment.room.dormitory
    template_obj = (
        ReservationTemplate.objects.filter(is_active=True, dormitory=dormitory).order_by("-uploaded_at").first()
        or ReservationTemplate.objects.filter(is_active=True, dormitory__isnull=True).order_by("-uploaded_at").first()
    )
    if not template_obj:
        return JsonResponse({"error": f'Keine aktive Reservierungsvorlage für "{dormitory.name}" oder als allgemeines Standardschreiben gefunden. Bitte im Admin-Bereich hochladen.'})

    # ── 1. Word-Vorlage befüllen ────────────────────────────────────────────
    try:
        from document.contexts import student_context, creator_context, meta_context
        from document.render import render_docx, upload_to_paperless
        student = assignment.student
        room = assignment.room
        context = {
            **student_context(student),
            **creator_context(request.user),
            **meta_context(),
            "wohnheim_name":     room.dormitory.name,
            "wohnheim_adresse":  room.dormitory.address,
            "zimmer_nummer":     room.number,
            "belegung_beginn":   assignment.start_date.strftime("%d.%m.%Y"),
            "belegung_ende":     assignment.end_date.strftime("%d.%m.%Y") if assignment.end_date else "offen",
        }
        file_bytes = render_docx(template_obj.template_file.path, context)
    except Exception as e:
        return JsonResponse({"error": f"Fehler beim Ausfüllen der Vorlage: {e}"})

    # ── 2. DOCX nach Paperless hochladen und auf Verarbeitung warten ───────
    title = (
        f"Reservation – {student.first_name} {student.last_name}"
        f" – Room {room.number} ({room.dormitory.name})"
        f" – {assignment.start_date.strftime('%d.%m.%Y')}"
    )
    filename = f"reservation_{student.last_name}_{student.first_name}_{assignment.start_date.strftime('%Y%m%d')}.docx"
    doc_id = upload_to_paperless(
        file_bytes=file_bytes,
        title=title,
        student_id=student.id,
        filename=filename,
    )
    if doc_id is None:
        return JsonResponse({"error": "Upload zu Paperless fehlgeschlagen oder Zeitüberschreitung. Bitte erneut versuchen."})

    assignment.paperless_confirmation_id = doc_id
    assignment.save(update_fields=["paperless_confirmation_id"])

    from django.urls import reverse
    return JsonResponse({"preview_url": reverse("services:paperless_preview", args=[doc_id])})


def q_active_or_ending_after(year_start):
    """Q-Objekt: Belegungen ohne Enddatum oder mit Enddatum nach dem angegebenen Datum."""
    from django.db.models import Q
    return Q(end_date__isnull=True) | Q(end_date__gte=year_start)


@login_required
def assignment_delete(request, public_id):
    """Zimmerbelegung loeschen (mit Bestaetigungsseite)."""
    assignment = get_object_or_404(RoomAssignment, public_id=public_id)
    room_pk = assignment.room.public_id
    if request.method == "POST":
        assignment.delete()
        messages.success(request, "Belegung wurde gelöscht.")
        return redirect("dormitory:room_detail", public_id=room_pk)
    return render(request, "dormitory/assignment_confirm_delete.html", {"assignment": assignment})
