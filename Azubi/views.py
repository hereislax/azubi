"""
Zentrale Views der Azubi-Anwendung.

Enthält Dashboard, Impressum, Datenschutz, Auswertungen, globale Suche,
die Dashboard-Konfigurations-API sowie Health-/Readiness-Endpunkte.
"""
# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from student.models import Student


@never_cache
def healthz(request):
    """Liveness-Probe: bestätigt nur, dass der Django-Prozess Anfragen verarbeitet.

    Bewusst minimalistisch – keine DB-Abfrage, keine externen Aufrufe. Damit
    bleibt der Endpunkt schnell und unabhängig von temporären Problemen
    nachgelagerter Dienste. Für die vollständige Readiness-Prüfung (DB, Cache)
    siehe ``/readyz``.
    """
    return HttpResponse('ok', content_type='text/plain')


@never_cache
def readyz(request):
    """Readiness-Probe: prüft Datenbank- und Cache-Verbindung.

    Liefert 200 mit JSON-Status, wenn alle Abhängigkeiten erreichbar sind;
    andernfalls 503. Geeignet für Loadbalancer-, Kubernetes- oder
    Blackbox-Exporter-Probes.
    """
    from django.db import connection
    from django.core.cache import cache

    checks = {}
    overall_ok = True

    # Datenbankverbindung prüfen (leichter SELECT 1, kein ORM)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['database'] = 'ok'
    except Exception as exc:
        checks['database'] = f'error: {exc.__class__.__name__}'
        overall_ok = False

    # Cache (Redis) per Roundtrip prüfen – Set + Get auf Marker-Key
    try:
        cache.set('healthcheck:readyz', '1', timeout=5)
        if cache.get('healthcheck:readyz') == '1':
            checks['cache'] = 'ok'
        else:
            checks['cache'] = 'error: roundtrip mismatch'
            overall_ok = False
    except Exception as exc:
        checks['cache'] = f'error: {exc.__class__.__name__}'
        overall_ok = False

    return JsonResponse(
        {'status': 'ok' if overall_ok else 'unhealthy', 'checks': checks},
        status=200 if overall_ok else 503,
    )


def impressum(request):
    from services.models import SiteConfiguration
    config = SiteConfiguration.get()
    return render(request, 'imprint.html', {'impressum_text': config.impressum_text})


def datenschutz(request):
    from services.models import SiteConfiguration
    config = SiteConfiguration.get()
    return render(request, 'dataprotection.html', {'datenschutz_text': config.datenschutz_text})


def barrierefreiheit(request):
    from services.models import SiteConfiguration
    config = SiteConfiguration.get()
    return render(request, 'accessibility.html', {
        'barrierefreiheit_text': config.barrierefreiheit_text,
    })


def acknowledgments(request):
    return render(request, 'acknowledgments.html')


@login_required
def index(request):
    # Students are redirected to their self-service portal
    if hasattr(request.user, 'student_profile'):
        return redirect('portal:home')

    from services.roles import (
        is_training_director, is_training_office, is_training_coordinator,
        is_training_responsible, get_chief_instructor,
    )

    today = date.today()
    two_weeks_window = today + timedelta(days=14)
    thirty_days = today + timedelta(days=30)

    is_leitung = is_training_director(request.user)
    is_referat = is_training_office(request.user)
    is_koord = is_training_coordinator(request.user)
    is_ps = is_training_responsible(request.user)

    # Koordination: Geburtstage nur für zugewiesene NKs
    birthday_student_qs = Student.objects.order_by('last_name', 'first_name')
    if is_koord and not (is_leitung or is_referat):
        from instructor.views import _get_coordination_area
        chief = get_chief_instructor(request.user)
        if chief and chief.coordination:
            from course.models import InternshipAssignment
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)
            koord_student_ids = (
                InternshipAssignment.objects
                .filter(unit_id__in=descendant_pks)
                .values_list('student_id', flat=True)
                .distinct()
            )
            birthday_student_qs = birthday_student_qs.filter(pk__in=koord_student_ids)
        else:
            birthday_student_qs = Student.objects.none()

    def _calc_age(dob, birthday_date):
        return birthday_date.year - dob.year

    birthdays_today = []
    birthdays_soon = []

    for student in birthday_student_qs:
        dob = student.date_of_birth
        if not dob:
            continue
        try:
            this_year = dob.replace(year=today.year)
        except ValueError:
            this_year = dob.replace(year=today.year, day=28)
        try:
            next_year_bday = dob.replace(year=today.year + 1)
        except ValueError:
            next_year_bday = dob.replace(year=today.year + 1, day=28)

        if this_year == today:
            birthdays_today.append({'student': student, 'age': _calc_age(dob, this_year)})
        elif today < this_year <= two_weeks_window:
            birthdays_soon.append({'student': student, 'date': this_year, 'age': _calc_age(dob, this_year)})
        elif today <= next_year_bday <= two_weeks_window:
            birthdays_soon.append({'student': student, 'date': next_year_bday, 'age': _calc_age(dob, next_year_bday)})

    birthdays_soon.sort(key=lambda x: x['date'])

    # Dashboard-Konfiguration laden
    from services.models import DashboardConfig
    dashboard_config, _ = DashboardConfig.objects.get_or_create(user=request.user)
    dashboard_type = 'leitung' if (is_leitung or is_referat) else ('koord' if is_koord else None)
    widget_config = dashboard_config.get_ordered_widgets(dashboard_type) if dashboard_type else []
    visible_widgets = {w['id'] for w in widget_config if w['visible']}

    ctx = {
        'birthdays_today': birthdays_today,
        'birthdays_soon': birthdays_soon,
        'today': today,
        'widget_config': widget_config,
        'visible_widgets': visible_widgets,
    }

    if is_leitung or is_referat:
        from django.db.models import Count, Q
        from course.models import (
            Course, ScheduleBlock, InternshipAssignment,
            BlockLetter, InternshipPlanLetter, StationLetter,
            ASSIGNMENT_STATUS_PENDING, ASSIGNMENT_STATUS_APPROVED, BLOCK_LETTER_STATUS_PENDING,
        )
        from proofoftraining.models import TrainingRecord, STATUS_SUBMITTED, STATUS_REJECTED
        from absence.models import (
            VacationRequest, SickLeave, StudentAbsenceState,
            STATUS_PENDING as VAC_PENDING,
        )
        from studyday.models import StudyDayRequest, STATUS_PENDING as STUDY_PENDING
        from assessment.models import Assessment, STATUS_PENDING as ASSESS_PENDING
        from intervention.models import Intervention, STATUS_OPEN, STATUS_IN_PROGRESS

        active_students = Student.objects.exclude(anonymized_at__isnull=False).count()
        active_courses_qs = Course.objects.filter(end_date__gte=today).order_by('end_date')
        active_courses = active_courses_qs.count()
        pending_training_count = TrainingRecord.objects.filter(status=STATUS_SUBMITTED).count()
        pending_assignments_count = InternshipAssignment.objects.filter(
            status=ASSIGNMENT_STATUS_PENDING
        ).count()
        pending_vacation_count = VacationRequest.objects.filter(status=VAC_PENDING).count()
        pending_studyday_count = StudyDayRequest.objects.filter(status=STUDY_PENDING).count()
        pending_assessment_count = Assessment.objects.filter(status=ASSESS_PENDING).count()
        open_interventions_qs = Intervention.objects.filter(
            status__in=[STATUS_OPEN, STATUS_IN_PROGRESS]
        )
        open_interventions_count = open_interventions_qs.count()

        upcoming_blocks = (
            ScheduleBlock.objects
            .filter(start_date__gte=today, start_date__lte=thirty_days)
            .select_related('course')
            .order_by('start_date')
        )

        pending_internships = (
            InternshipAssignment.objects
            .filter(status=ASSIGNMENT_STATUS_PENDING)
            .select_related('student', 'unit', 'schedule_block__course')
            .order_by('schedule_block__start_date')[:10]
        )

        pending_block_letters = [
            {'obj': l, 'type': 'Zuweisungsschreiben'}
            for l in BlockLetter.objects.filter(status=BLOCK_LETTER_STATUS_PENDING)
                .select_related('schedule_block__course')
        ]
        pending_plan_letters = [
            {'obj': l, 'type': 'Praktikumsplan'}
            for l in InternshipPlanLetter.objects.filter(status=BLOCK_LETTER_STATUS_PENDING)
                .select_related('schedule_block__course')
        ]
        pending_station_letters = [
            {'obj': l, 'type': 'Stationsschreiben'}
            for l in StationLetter.objects.filter(status=BLOCK_LETTER_STATUS_PENDING)
                .select_related('schedule_block__course')
        ]
        pending_letters = pending_block_letters + pending_plan_letters + pending_station_letters

        recently_rejected = (
            TrainingRecord.objects
            .filter(status=STATUS_REJECTED)
            .select_related('student')
            .order_by('-reviewed_at')[:10]
        )

        ending_soon = (
            InternshipAssignment.objects
            .filter(
                status=ASSIGNMENT_STATUS_APPROVED,
                end_date__gte=today,
                end_date__lte=two_weeks_window,
            )
            .select_related('student', 'unit', 'schedule_block__course')
            .order_by('end_date')[:15]
        )

        open_interventions = (
            open_interventions_qs
            .select_related('student', 'category')
            .order_by('followup_date')[:10]
        )

        # ── Fehlzeiten-Ampel + Kursfortschritt (bulk, kein N+1) ──────────────
        # Alle Studierenden aktiver Kurse in einer Query holen
        all_course_students = list(
            Student.objects
            .filter(course__in=active_courses_qs, anonymized_at__isnull=True)
            .prefetch_related('absence_state')
            .only('pk', 'course_id')
        )
        # Anzahl NK je Kurs
        student_counts = {}
        students_by_course = {}
        for s in all_course_students:
            student_counts[s.course_id] = student_counts.get(s.course_id, 0) + 1
            students_by_course.setdefault(s.course_id, []).append(s)

        # Offene Krankmeldungen aller NK in einer Query
        all_student_pks = [s.pk for s in all_course_students]
        open_sick_ids = set(
            SickLeave.objects
            .filter(student_id__in=all_student_pks, end_date__isnull=True)
            .values_list('student_id', flat=True)
        )

        fehlzeiten_kurse = []
        course_progress = []
        for course in active_courses_qs:
            students = students_by_course.get(course.pk, [])
            total_days = max(1, (course.end_date - course.start_date).days)
            elapsed = max(0, (today - course.start_date).days)
            pct = min(100, int(elapsed / total_days * 100))
            course_progress.append({
                'course': course,
                'pct': pct,
                'days_left': (course.end_date - today).days,
                'student_count': len(students),
            })
            if not students:
                continue
            traffic = {'green': 0, 'yellow': 0, 'red': 0, 'unknown': 0}
            for s in students:
                try:
                    tl = s.absence_state.traffic_light
                except StudentAbsenceState.DoesNotExist:
                    tl = 'unknown'
                traffic[tl] += 1
            fehlzeiten_kurse.append({
                'course': course,
                'green': traffic['green'],
                'yellow': traffic['yellow'],
                'red': traffic['red'],
                'unknown': traffic['unknown'],
                'open_sick': sum(1 for s in students if s.pk in open_sick_ids),
                'total': len(students),
            })

        # ── Wohnheim-Belegung ─────────────────────────────────────────────────
        dormitory_stats = []
        try:
            from dormitory.models import Dormitory, RoomAssignment
            for dorm in Dormitory.objects.prefetch_related('rooms').order_by('name'):
                total_capacity = sum(r.capacity for r in dorm.rooms.all())
                if total_capacity == 0:
                    continue
                occupied = RoomAssignment.objects.filter(
                    room__dormitory=dorm,
                    start_date__lte=today,
                ).filter(
                    Q(end_date__isnull=True) | Q(end_date__gte=today)
                ).count()
                free = total_capacity - occupied
                pct = int(occupied / total_capacity * 100)
                dormitory_stats.append({
                    'dorm': dorm,
                    'capacity': total_capacity,
                    'occupied': occupied,
                    'free': free,
                    'pct': pct,
                })
        except Exception:
            pass

        # ── Stationsauslastung (Einheiten mit Kapazitätslimit) ────────────────
        station_utilization = []
        try:
            from organisation.models import OrganisationalUnit
            units_with_limit = OrganisationalUnit.objects.filter(
                max_capacity__isnull=False, max_capacity__gt=0
            )
            for unit in units_with_limit:
                current = InternshipAssignment.objects.filter(
                    unit=unit,
                    status=ASSIGNMENT_STATUS_APPROVED,
                    start_date__lte=today,
                    end_date__gte=today,
                ).count()
                if current == 0:
                    continue
                pct = int(current / unit.max_capacity * 100)
                station_utilization.append({
                    'unit': unit,
                    'current': current,
                    'capacity': unit.max_capacity,
                    'free': max(0, unit.max_capacity - current),
                    'pct': min(100, pct),
                })
            station_utilization.sort(key=lambda x: x['pct'], reverse=True)
            station_utilization = station_utilization[:8]
        except Exception:
            pass

        ctx.update({
            'show_leitung_dashboard': True,
            'active_students': active_students,
            'active_courses': active_courses,
            'pending_training_count': pending_training_count,
            'pending_assignments_count': pending_assignments_count,
            'pending_vacation_count': pending_vacation_count,
            'pending_studyday_count': pending_studyday_count,
            'pending_assessment_count': pending_assessment_count,
            'open_interventions_count': open_interventions_count,
            'upcoming_blocks': upcoming_blocks,
            'pending_internships': pending_internships,
            'pending_letters': pending_letters,
            'recently_rejected': recently_rejected,
            'course_progress': course_progress,
            'dormitory_stats': dormitory_stats,
            'station_utilization': station_utilization,
            'ending_soon': ending_soon,
            'open_interventions': open_interventions,
            'fehlzeiten_kurse': fehlzeiten_kurse,
            'two_weeks_window': two_weeks_window,
        })

    elif is_koord:
        from instructor.views import _get_coordination_area
        from course.models import InternshipAssignment, ASSIGNMENT_STATUS_PENDING, ASSIGNMENT_STATUS_APPROVED
        from proofoftraining.models import TrainingRecord, STATUS_SUBMITTED
        from absence.models import StudentAbsenceState

        chief = get_chief_instructor(request.user)
        koord_training = TrainingRecord.objects.none()
        koord_pending = InternshipAssignment.objects.none()
        koord_ending_soon = InternshipAssignment.objects.none()
        koord_fehlzeiten = []
        koord_student_count = 0
        koord_pending_count = 0
        koord_training_count = 0
        koord_red_count = 0

        if chief and chief.coordination:
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)

            koord_student_pks = list(
                InternshipAssignment.objects
                .filter(unit_id__in=descendant_pks)
                .values_list('student_id', flat=True)
                .distinct()
            )
            koord_student_count = len(koord_student_pks)

            koord_training = (
                TrainingRecord.objects
                .filter(status=STATUS_SUBMITTED, student_id__in=koord_student_pks)
                .select_related('student')
                .order_by('submitted_at')[:10]
            )
            koord_training_count = TrainingRecord.objects.filter(
                status=STATUS_SUBMITTED, student_id__in=koord_student_pks
            ).count()

            koord_pending = (
                InternshipAssignment.objects
                .filter(status=ASSIGNMENT_STATUS_PENDING, unit_id__in=descendant_pks)
                .select_related('student', 'unit', 'schedule_block__course')
                .order_by('schedule_block__start_date')[:10]
            )
            koord_pending_count = InternshipAssignment.objects.filter(
                status=ASSIGNMENT_STATUS_PENDING, unit_id__in=descendant_pks
            ).count()

            koord_ending_soon = (
                InternshipAssignment.objects
                .filter(
                    status=ASSIGNMENT_STATUS_APPROVED,
                    unit_id__in=descendant_pks,
                    end_date__gte=today,
                    end_date__lte=two_weeks_window,
                )
                .select_related('student', 'unit')
                .order_by('end_date')[:10]
            )

            # Fehlzeiten: gelbe + rote NKs im Koord-Bereich
            for s in (
                Student.objects
                .filter(pk__in=koord_student_pks, anonymized_at__isnull=True)
                .prefetch_related('absence_state')
                .order_by('last_name', 'first_name')
            ):
                try:
                    tl = s.absence_state.traffic_light
                except StudentAbsenceState.DoesNotExist:
                    tl = 'unknown'
                if tl in ('yellow', 'red'):
                    koord_fehlzeiten.append({'student': s, 'tl': tl})
                if tl == 'red':
                    koord_red_count += 1

        ctx.update({
            'show_koord_dashboard': True,
            'koord_training': koord_training,
            'koord_training_count': koord_training_count,
            'koord_pending': koord_pending,
            'koord_pending_count': koord_pending_count,
            'koord_ending_soon': koord_ending_soon,
            'koord_fehlzeiten': koord_fehlzeiten,
            'koord_student_count': koord_student_count,
            'koord_red_count': koord_red_count,
        })

    elif is_ps:
        # Ausbildungsverantwortliche: nur freigegebene Nachwuchskräfte
        from student.models import TrainingResponsibleAccess
        from proofoftraining.models import TrainingRecord, STATUS_SUBMITTED

        allowed_student_ids = TrainingResponsibleAccess.objects.filter(
            user=request.user
        ).values_list('student_id', flat=True)

        ps_training = (
            TrainingRecord.objects
            .filter(status=STATUS_SUBMITTED, student_id__in=allowed_student_ids)
            .select_related('student')
            .order_by('submitted_at')
        )

        ctx.update({
            'show_ps_dashboard': True,
            'ps_training': ps_training,
        })

    return render(request, 'index.html', ctx)


def _require_report_access(user):
    """Schutz für alle Reporting-Views: nur Ausbildungsleitung + Ausbildungsreferat."""
    from django.core.exceptions import PermissionDenied
    from services.roles import is_training_director, is_training_office
    if not (user.is_authenticated and (
        user.is_staff or is_training_director(user) or is_training_office(user)
    )):
        raise PermissionDenied


@login_required
def auswertungen(request):
    """Reports-Hub: Liste aller Reports nach Kategorie + gespeicherte Sichten + Custom Reports."""
    _require_report_access(request.user)
    from services.reports import registry as report_registry
    from services.models import SavedReportView, CustomReport
    from django.db.models import Q

    reports_by_cat = {}
    for cls in report_registry.all_reports():
        reports_by_cat.setdefault(cls.category, []).append({
            'slug': cls.slug, 'name': cls.name,
            'description': cls.description, 'is_custom': False,
        })

    custom_reports = (
        CustomReport.objects
        .filter(Q(owner=request.user) | Q(shared=True))
        .select_related('owner')
        .order_by('category', 'name')
    )
    for cr in custom_reports:
        reports_by_cat.setdefault(cr.category, []).append({
            'slug': cr.slug, 'name': cr.name, 'description': cr.description,
            'is_custom': True, 'owner': cr.owner, 'pk': cr.pk,
            'is_own': cr.owner_id == request.user.pk,
        })

    saved_views = (
        SavedReportView.objects
        .filter(Q(owner=request.user) | Q(shared=True))
        .select_related('owner')
        .order_by('report_slug', 'name')
    )
    saved_by_slug = {}
    for sv in saved_views:
        saved_by_slug.setdefault(sv.report_slug, []).append(sv)

    return render(request, 'reports/hub.html', {
        'reports_by_cat': sorted(reports_by_cat.items()),
        'saved_by_slug':  saved_by_slug,
    })


@login_required
def report_detail(request, slug):
    """Detail-Ansicht eines Reports: Filter + Tabelle (+ optional Chart).

    Unterstützt zwei Arten von Reports:
    - Code-Reports (slug aus services.reports.registry)
    - Custom-Reports (slug = ``custom-<pk>``, Definition aus DB)
    """
    _require_report_access(request.user)
    from services.reports import registry as report_registry

    is_custom = slug.startswith('custom-')
    custom_instance = None

    if is_custom:
        from services.models import CustomReport
        from services.reports.engine import execute_custom_report, InvalidReportDefinition
        from services.reports.base import BaseReport as _BR
        from django.shortcuts import get_object_or_404
        from django.http import Http404
        from django.db.models import Q
        try:
            pk = int(slug.removeprefix('custom-'))
        except ValueError:
            raise Http404
        custom_instance = get_object_or_404(
            CustomReport.objects.filter(Q(owner=request.user) | Q(shared=True)),
            pk=pk,
        )

        # Adapter-Klasse, damit Template-Variablen identisch zu Code-Reports bleiben
        class _CustomReportAdapter(_BR):
            slug = custom_instance.slug
            name = custom_instance.name
            category = custom_instance.category
            description = custom_instance.description
            filters = []  # Custom-Reports haben keine User-Filter (Filter sind in Definition fix)
            chart = None
            def __init__(self, definition):
                self._definition = definition
                cols, rows = execute_custom_report(definition, limit=10000)
                self.columns = cols
                self._rows = rows
            def get_rows(self, filter_values):
                return self._rows

        try:
            report = _CustomReportAdapter(custom_instance.definition or {})
        except InvalidReportDefinition as exc:
            from django.contrib import messages as _msgs
            _msgs.error(request, f'Report-Definition ungültig: {exc}')
            from django.shortcuts import redirect
            return redirect('auswertungen')
    else:
        report_cls = report_registry.get_report(slug)
        if report_cls is None:
            from django.http import Http404
            raise Http404('Report nicht gefunden.')
        report = report_cls()

    filter_values = report.parse_filters(request.GET)
    selected_cols = request.GET.getlist('col') or None
    visible = report.visible_columns(selected_cols)
    rows = report.get_rows(filter_values)

    saved_view = None
    saved_view_pk = request.GET.get('view')
    if saved_view_pk:
        from services.models import SavedReportView
        try:
            saved_view = SavedReportView.objects.get(pk=int(saved_view_pk))
        except (SavedReportView.DoesNotExist, ValueError):
            pass

    chart_data = None
    if report.chart and rows:
        c = report.chart_dict()
        chart_data = {
            'type':   c['type'],
            'labels': [str(r.get(c['x'], '')) for r in rows[:50]],
            'data':   [r.get(c['y'], 0) or 0 for r in rows[:50]],
            'label':  c.get('label') or c['y'],
        }

    return render(request, 'reports/detail.html', {
        'report':           report,
        'all_columns':      report.columns,
        'visible_cols':     visible,
        'visible_keys':     [c.key for c in visible],
        'filter_values':    filter_values,
        'rows':             rows,
        'row_count':        len(rows),
        'chart_data':       chart_data,
        'saved_view':       saved_view,
        'query_string':     request.GET.urlencode(),
        'custom_instance':  custom_instance,
    })


@login_required
def report_export(request, slug, fmt):
    """Excel- (xlsx) oder CSV-Export eines Reports mit aktuellen Filtern/Spalten."""
    _require_report_access(request.user)
    from django.http import HttpResponse, Http404
    from django.shortcuts import get_object_or_404
    from django.db.models import Q
    from services.reports import registry as report_registry
    from services.reports.exports import report_to_xlsx, report_to_csv
    from services.reports.engine import execute_custom_report
    from datetime import date as _d

    if slug.startswith('custom-'):
        from services.models import CustomReport
        from services.reports.base import BaseReport as _BR
        try:
            pk = int(slug.removeprefix('custom-'))
        except ValueError:
            raise Http404
        custom_instance = get_object_or_404(
            CustomReport.objects.filter(Q(owner=request.user) | Q(shared=True)),
            pk=pk,
        )
        cols, rows = execute_custom_report(custom_instance.definition or {}, limit=10000)
        class _Tmp(_BR):
            name = custom_instance.name
            columns = cols
        report = _Tmp()
        report.name = custom_instance.name
        visible = cols
    else:
        report_cls = report_registry.get_report(slug)
        if report_cls is None:
            raise Http404
        report = report_cls()
        filter_values = report.parse_filters(request.GET)
        selected_cols = request.GET.getlist('col') or None
        visible = report.visible_columns(selected_cols)
        rows = report.get_rows(filter_values)

    base_name = f'{slug}_{_d.today().isoformat()}'
    if fmt == 'xlsx':
        data = report_to_xlsx(report, rows, visible)
        ct = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = f'{base_name}.xlsx'
    elif fmt == 'csv':
        data = report_to_csv(rows, visible)
        ct = 'text/csv; charset=utf-8'
        filename = f'{base_name}.csv'
    else:
        raise Http404
    resp = HttpResponse(data, content_type=ct)
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def saved_view_save(request, slug):
    """Speichert die aktuellen Filter/Spalten als SavedReportView."""
    _require_report_access(request.user)
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.http import Http404
    from services.reports import registry as report_registry
    from services.models import SavedReportView

    if request.method != 'POST':
        return redirect('report_detail', slug=slug)

    report_cls = report_registry.get_report(slug)
    if report_cls is None:
        raise Http404

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Bitte einen Namen für die Sicht angeben.')
        return redirect(f'/auswertungen/{slug}/?{request.POST.get("query","")}')

    description = request.POST.get('description', '').strip()
    shared = request.POST.get('shared') in ('1', 'on', 'true')

    # Filter und Spalten aus dem aktuellen Query-String der Detail-View aufnehmen
    from urllib.parse import parse_qsl
    qs = dict(parse_qsl(request.POST.get('query', ''), keep_blank_values=True))
    filters_dict = {k: v for k, v in qs.items() if k != 'col'}
    cols = [c for c in qs.values() if False]  # placeholder, wird unten ersetzt
    # multi-Werte (cols) korrekt extrahieren
    from urllib.parse import parse_qs as _parse_qs
    multi = _parse_qs(request.POST.get('query', ''), keep_blank_values=True)
    cols = multi.get('col', [])

    sv = SavedReportView.objects.create(
        report_slug=slug,
        name=name,
        description=description,
        owner=request.user,
        filters_json=filters_dict,
        columns_json=cols,
        shared=shared,
    )
    messages.success(request, f'Sicht „{sv.name}" gespeichert.')
    return redirect(f'/auswertungen/{slug}/?view={sv.pk}&{request.POST.get("query","")}')


@login_required
def saved_view_open(request, pk):
    """Öffnet eine SavedReportView (lädt Filter + Spalten und leitet zur Detail-View)."""
    _require_report_access(request.user)
    from django.shortcuts import get_object_or_404, redirect
    from django.db.models import Q
    from services.models import SavedReportView
    from urllib.parse import urlencode

    sv = get_object_or_404(
        SavedReportView.objects.filter(Q(owner=request.user) | Q(shared=True)),
        pk=pk,
    )
    params = list((sv.filters_json or {}).items())
    for col_key in (sv.columns_json or []):
        params.append(('col', col_key))
    params.append(('view', sv.pk))
    return redirect(f'/auswertungen/{sv.report_slug}/?{urlencode(params)}')


@login_required
def saved_view_delete(request, pk):
    """Löscht eine SavedReportView (nur Eigentümer)."""
    _require_report_access(request.user)
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    from services.models import SavedReportView

    sv = get_object_or_404(SavedReportView, pk=pk, owner=request.user)
    if request.method == 'POST':
        slug = sv.report_slug
        sv.delete()
        messages.success(request, 'Sicht wurde gelöscht.')
        return redirect('report_detail', slug=slug)
    return render(request, 'reports/saved_view_delete.html', {'view': sv})


@login_required
def custom_report_builder(request, pk: int | None = None):
    """Frontend-Query-Builder: Datenquelle wählen, Felder/Filter/Aggregationen, speichern."""
    _require_report_access(request.user)
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    from services.models import CustomReport
    from services.reports.datasources import all_datasources, get_datasource, OPERATORS_BY_TYPE, AGGREGATIONS
    from services.reports.engine import execute_custom_report, InvalidReportDefinition
    import json

    instance = None
    if pk:
        instance = get_object_or_404(CustomReport, pk=pk)
        if instance.owner_id != request.user.pk and not instance.shared:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')
        try:
            definition = json.loads(request.POST.get('definition_json', '{}') or '{}')
        except json.JSONDecodeError:
            definition = {}

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'Eigene Reports').strip() or 'Eigene Reports'
        shared = request.POST.get('shared') in ('1', 'on', 'true')

        if action == 'save':
            if not name:
                messages.error(request, 'Bitte einen Namen angeben.')
            elif not definition.get('datasource'):
                messages.error(request, 'Bitte eine Datenquelle wählen.')
            else:
                if instance is None:
                    instance = CustomReport(owner=request.user)
                elif instance.owner_id != request.user.pk:
                    # Geteilten Report kopieren statt überschreiben
                    instance = CustomReport(owner=request.user)
                instance.name = name
                instance.description = description
                instance.category = category
                instance.shared = shared
                instance.definition = definition
                instance.save()
                messages.success(request, f'Eigener Report „{instance.name}" gespeichert.')
                return redirect('report_detail', slug=instance.slug)

        # Preview
        preview_columns, preview_rows = [], []
        preview_error = None
        if definition.get('datasource'):
            try:
                preview_columns, preview_rows = execute_custom_report(definition, limit=50)
            except InvalidReportDefinition as exc:
                preview_error = str(exc)
        return render(request, 'reports/builder.html', {
            'instance':            instance,
            'name':                name,
            'description':         description,
            'category':            category,
            'shared':              shared,
            'definition_json':     json.dumps(definition),
            'datasources':         all_datasources(),
            'operators_by_type':   OPERATORS_BY_TYPE,
            'aggregations':        AGGREGATIONS,
            'preview_columns':     preview_columns,
            'preview_rows':        preview_rows,
            'preview_error':       preview_error,
            'datasource_fields_json': _datasource_fields_json(),
        })

    # GET
    if instance:
        definition = instance.definition or {}
        name = instance.name
        description = instance.description
        category = instance.category
        shared = instance.shared
    else:
        definition = {'datasource': '', 'select': [], 'filters': [],
                      'group_by': [], 'aggregations': [], 'order_by': [], 'limit': 1000}
        name = description = ''
        category = 'Eigene Reports'
        shared = False

    return render(request, 'reports/builder.html', {
        'instance':            instance,
        'name':                name,
        'description':         description,
        'category':            category,
        'shared':              shared,
        'definition_json':     json.dumps(definition),
        'datasources':         all_datasources(),
        'operators_by_type':   OPERATORS_BY_TYPE,
        'aggregations':        AGGREGATIONS,
        'preview_columns':     [],
        'preview_rows':        [],
        'preview_error':       None,
        'datasource_fields_json': _datasource_fields_json(),
    })


def _datasource_fields_json():
    """Liefert die DataSource-Felder als JSON-String für das Frontend-Builder-JS."""
    import json
    from services.reports.datasources import all_datasources, OPERATORS_BY_TYPE
    out = {}
    for ds in all_datasources():
        out[ds.key] = {
            'label':  ds.label,
            'fields': [
                {'path': f.path, 'label': f.label, 'type': f.type,
                 'operators': OPERATORS_BY_TYPE.get(f.type, []),
                 'choices': f.choices or []}
                for f in ds.available_fields
            ],
            'default_select': ds.default_select,
        }
    return json.dumps(out)


@login_required
def custom_report_delete(request, pk: int):
    """Löscht einen eigenen CustomReport (nur Eigentümer)."""
    _require_report_access(request.user)
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    from services.models import CustomReport
    inst = get_object_or_404(CustomReport, pk=pk, owner=request.user)
    if request.method == 'POST':
        inst.delete()
        messages.success(request, 'Eigener Report wurde gelöscht.')
        return redirect('auswertungen')
    return render(request, 'reports/custom_delete.html', {'instance': inst})


@login_required
def dashboard_config_save(request):
    """AJAX-Endpoint: Dashboard-Widget-Konfiguration speichern."""
    import json
    from django.http import JsonResponse
    from services.models import DashboardConfig

    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False}, status=400)

    config, _ = DashboardConfig.objects.get_or_create(user=request.user)
    if 'widget_order' in data:
        config.widget_order = data['widget_order']
    if 'hidden_widgets' in data:
        config.hidden_widgets = data['hidden_widgets']
    config.save()
    return JsonResponse({'ok': True})


@login_required
def global_search(request):
    from django.db.models import Q
    from services.roles import (
        is_training_director, is_training_office,
        is_training_coordinator, is_training_responsible,
        get_chief_instructor,
    )

    query = request.GET.get('q', '').strip()
    results = {}

    is_leitung = is_training_director(request.user)
    is_referat = is_training_office(request.user)
    is_koord = is_training_coordinator(request.user)
    is_ps = is_training_responsible(request.user)
    can_see_all = is_leitung or is_referat

    # Koordinationsbereich ermitteln (unit PKs + instructor PKs)
    koord_unit_pks = None
    koord_instructor_pks = None
    if is_koord and not can_see_all:
        from instructor.views import _get_coordination_area
        from course.models import InternshipAssignment
        chief = get_chief_instructor(request.user)
        if chief and chief.coordination:
            descendant_pks, _, _ = _get_coordination_area(chief.coordination)
            koord_unit_pks = descendant_pks
            koord_instructor_pks = list(
                InternshipAssignment.objects
                .filter(unit_id__in=descendant_pks, instructor__isnull=False)
                .values_list('instructor_id', flat=True)
                .distinct()
            )
        else:
            koord_unit_pks = []
            koord_instructor_pks = []

    if query:
        # ── Nachwuchskräfte ───────────────────────────────────────────────
        if can_see_all or is_koord or is_ps:
            qs = Student.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email_id__icontains=query)
            ).select_related('course', 'status').order_by('last_name', 'first_name')

            if is_koord and not can_see_all:
                if koord_unit_pks:
                    from course.models import InternshipAssignment
                    student_ids = (
                        InternshipAssignment.objects
                        .filter(unit_id__in=koord_unit_pks)
                        .values_list('student_id', flat=True)
                        .distinct()
                    )
                    qs = qs.filter(pk__in=student_ids)
                else:
                    qs = qs.none()
            elif is_ps and not can_see_all:
                from student.models import TrainingResponsibleAccess
                allowed_ids = TrainingResponsibleAccess.objects.filter(
                    user=request.user
                ).values_list('student_id', flat=True)
                qs = qs.filter(pk__in=allowed_ids)

            results['students'] = qs[:20]

        # ── Praxistutoren ─────────────────────────────────────────────────
        if can_see_all or is_koord:
            from instructor.models import Instructor
            qs = Instructor.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query)
            ).select_related('unit')

            if is_koord and not can_see_all:
                if koord_instructor_pks is not None:
                    qs = qs.filter(pk__in=koord_instructor_pks)
                else:
                    qs = qs.none()

            results['instructors'] = qs[:20]

        # ── Einheiten & Kurse: nur für Leitung / Referat ──────────────────
        if can_see_all:
            from organisation.models import OrganisationalUnit
            from course.models import Course

            results['units'] = OrganisationalUnit.objects.filter(
                Q(name__icontains=query) | Q(label__icontains=query)
            )[:20]

            results['courses'] = Course.objects.filter(
                Q(title__icontains=query)
            )[:20]

    return render(request, 'search.html', {
        'query': query,
        'results': results,
    })
