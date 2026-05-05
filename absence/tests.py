# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tests für Urlaubs- und Krankmeldungs-Berechnung."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.apps import apps

from absence.models import (
    AbsenceSettings,
    SickLeave,
    VacationRequest,
    _get_public_holidays,
    _working_days_between,
)


# ─────────────────────────────────────────────────────────────────────────────
# Smoke
# ─────────────────────────────────────────────────────────────────────────────

def test_app_loaded():
    assert apps.get_app_config("absence") is not None


# ─────────────────────────────────────────────────────────────────────────────
# _working_days_between — Pure-Function-Tests, keine DB
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkingDaysBetween:
    """Reine Arithmetik – keine Feiertagslogik, keine DB."""

    def test_single_weekday(self):
        # Montag, 06.05.2024
        d = date(2024, 5, 6)
        assert _working_days_between(d, d) == 1

    def test_single_saturday_returns_zero(self):
        d = date(2024, 5, 4)  # Samstag
        assert _working_days_between(d, d) == 0

    def test_single_sunday_returns_zero(self):
        d = date(2024, 5, 5)  # Sonntag
        assert _working_days_between(d, d) == 0

    def test_full_workweek_monday_to_friday(self):
        # 06.05.2024 (Mo) – 10.05.2024 (Fr)
        assert _working_days_between(date(2024, 5, 6), date(2024, 5, 10)) == 5

    def test_full_week_includes_weekend(self):
        # 06.05.2024 (Mo) – 12.05.2024 (So) → trotzdem nur 5 Arbeitstage
        assert _working_days_between(date(2024, 5, 6), date(2024, 5, 12)) == 5

    def test_two_weeks(self):
        # 06.05.2024 (Mo) – 17.05.2024 (Fr) → 10 Arbeitstage
        assert _working_days_between(date(2024, 5, 6), date(2024, 5, 17)) == 10

    def test_holiday_excluded(self):
        # 06.05.2024–10.05.2024 mit Mittwoch (08.05.) als Feiertag → 4 statt 5
        holidays = frozenset({date(2024, 5, 8)})
        assert _working_days_between(date(2024, 5, 6), date(2024, 5, 10), holidays) == 4

    def test_holiday_on_weekend_does_not_double_subtract(self):
        # Feiertag fällt auf Samstag → kein Effekt
        holidays = frozenset({date(2024, 5, 11)})
        assert _working_days_between(date(2024, 5, 6), date(2024, 5, 12), holidays) == 5

    def test_end_before_start_returns_zero(self):
        assert _working_days_between(date(2024, 5, 10), date(2024, 5, 6)) == 0

    def test_none_start_returns_zero(self):
        assert _working_days_between(None, date(2024, 5, 10)) == 0

    def test_none_end_returns_zero(self):
        assert _working_days_between(date(2024, 5, 6), None) == 0

    def test_spans_year_boundary(self):
        # 30.12.2024 (Mo) – 03.01.2025 (Fr) → 5 Arbeitstage (ohne Feiertage)
        assert _working_days_between(date(2024, 12, 30), date(2025, 1, 3)) == 5


# ─────────────────────────────────────────────────────────────────────────────
# _get_public_holidays — braucht DB für AbsenceSettings
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestGetPublicHolidays:
    """Feiertagsbestimmung über `holidays`-Library + AbsenceSettings-Singleton."""

    def test_bundesweit_includes_tag_der_deutschen_einheit(self):
        AbsenceSettings.objects.create(pk=1, holiday_state='')
        result = _get_public_holidays(date(2024, 1, 1), date(2024, 12, 31))
        assert date(2024, 10, 3) in result  # Tag der Deutschen Einheit

    def test_bayern_includes_heilige_drei_koenige(self):
        AbsenceSettings.objects.create(pk=1, holiday_state='BY')
        result = _get_public_holidays(date(2024, 1, 1), date(2024, 1, 31))
        assert date(2024, 1, 6) in result  # nur in BY/BW/ST

    def test_berlin_does_not_include_heilige_drei_koenige(self):
        AbsenceSettings.objects.create(pk=1, holiday_state='BE')
        result = _get_public_holidays(date(2024, 1, 1), date(2024, 1, 31))
        assert date(2024, 1, 6) not in result

    def test_no_settings_returns_bundesweit(self):
        # Ohne AbsenceSettings-Eintrag: state default '' → bundesweite Feiertage
        result = _get_public_holidays(date(2024, 1, 1), date(2024, 12, 31))
        assert date(2024, 10, 3) in result


# ─────────────────────────────────────────────────────────────────────────────
# VacationRequest.duration_working_days — Property
# ─────────────────────────────────────────────────────────────────────────────

class TestVacationRequestDuration:
    """Tests ohne DB-Save; mockt _get_public_holidays um AbsenceSettings zu umgehen."""

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_simple_week(self, _mock):
        vr = VacationRequest(start_date=date(2024, 5, 6), end_date=date(2024, 5, 10))
        assert vr.duration_working_days == 5

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_includes_weekend_correctly(self, _mock):
        # Mo–So: 5 Arbeitstage
        vr = VacationRequest(start_date=date(2024, 5, 6), end_date=date(2024, 5, 12))
        assert vr.duration_working_days == 5

    @patch("absence.models._get_public_holidays", return_value=frozenset({date(2024, 5, 8)}))
    def test_subtracts_holiday(self, _mock):
        vr = VacationRequest(start_date=date(2024, 5, 6), end_date=date(2024, 5, 10))
        assert vr.duration_working_days == 4

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_single_day_weekday(self, _mock):
        vr = VacationRequest(start_date=date(2024, 5, 6), end_date=date(2024, 5, 6))
        assert vr.duration_working_days == 1


# ─────────────────────────────────────────────────────────────────────────────
# VacationRequest.effective_working_days — Override-Logik
# ─────────────────────────────────────────────────────────────────────────────

class TestEffectiveWorkingDays:

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_returns_calculated_when_no_manual(self, _mock):
        vr = VacationRequest(
            start_date=date(2024, 5, 6),
            end_date=date(2024, 5, 10),
            manual_working_days=None,
        )
        assert vr.effective_working_days == 5

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_manual_overrides_calculation(self, _mock):
        vr = VacationRequest(
            start_date=date(2024, 5, 6),
            end_date=date(2024, 5, 10),
            manual_working_days=3,
        )
        assert vr.effective_working_days == 3

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_manual_zero_is_respected(self, _mock):
        # 0 ist ein gültiger manueller Wert (z.B. Sonderregelung)
        vr = VacationRequest(
            start_date=date(2024, 5, 6),
            end_date=date(2024, 5, 10),
            manual_working_days=0,
        )
        assert vr.effective_working_days == 0


# ─────────────────────────────────────────────────────────────────────────────
# SickLeave.duration_working_days
# ─────────────────────────────────────────────────────────────────────────────

class TestSickLeaveDuration:

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_closed_sick_leave(self, _mock):
        sl = SickLeave(start_date=date(2024, 5, 6), end_date=date(2024, 5, 10))
        assert sl.duration_working_days == 5

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_open_sick_leave_uses_today(self, _mock):
        # Offene Krankmeldung → end = date.today()
        start = date.today() - timedelta(days=7)
        sl = SickLeave(start_date=start, end_date=None)
        result = sl.duration_working_days
        assert 0 < result <= 8

    @patch("absence.models._get_public_holidays", return_value=frozenset())
    def test_single_day_weekday(self, _mock):
        sl = SickLeave(start_date=date(2024, 5, 6), end_date=date(2024, 5, 6))
        assert sl.duration_working_days == 1


# ─────────────────────────────────────────────────────────────────────────────
# Standort-Resolver: location & holiday_state für Antragszeitpunkt
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_student(db):
    """Factory für minimalen Student mit optionalem Course."""
    from student.models import Student
    from course.models import Course

    def _make(course=None, **kwargs):
        defaults = dict(
            first_name="Test",
            last_name="Person",
            date_of_birth=date(2000, 1, 1),
            place_of_birth="Berlin",
        )
        defaults.update(kwargs)
        if course:
            defaults["course"] = course
        return Student.objects.create(**defaults)

    return _make


@pytest.fixture
def make_course(db):
    """Factory für minimalen Course."""
    from course.models import Course
    counter = {"n": 0}

    def _make(**kwargs):
        counter["n"] += 1
        defaults = dict(
            title=f"TEST-COURSE-{counter['n']}",
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
        )
        defaults.update(kwargs)
        return Course.objects.create(**defaults)

    return _make


@pytest.fixture
def make_location(db):
    """Factory für Location mit Adresse + optionalem Bundesland (auf der Adresse)."""
    from organisation.models import Location
    from services.models import Adress

    def _make(name="Standort Test", holiday_state=""):
        address = Adress.objects.create(
            street="Teststraße",
            house_number="1",
            zip_code="10115",
            city="Berlin",
            holiday_state=holiday_state,
        )
        return Location.objects.create(name=name, address=address)

    return _make


@pytest.fixture
def make_block(db):
    """Factory für ScheduleBlock."""
    from course.models import ScheduleBlock

    def _make(course, location=None, start=None, end=None):
        return ScheduleBlock.objects.create(
            course=course,
            name="Test-Block",
            location=location,
            start_date=start or date(2024, 5, 1),
            end_date=end or date(2024, 5, 31),
        )

    return _make


@pytest.mark.django_db
class TestResolveLocation:
    """`_resolve_location` findet Standort über InternshipAssignment > ScheduleBlock."""

    def test_returns_location_from_schedule_block(
        self, make_student, make_course, make_location, make_block
    ):
        from absence.models import _resolve_location
        loc = make_location("Bundesamt Berlin", holiday_state="BE")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc, start=date(2024, 5, 1), end=date(2024, 5, 31))

        result = _resolve_location(student, date(2024, 5, 15))
        assert result == loc

    def test_returns_none_outside_block_period(
        self, make_student, make_course, make_location, make_block
    ):
        from absence.models import _resolve_location
        loc = make_location("X", holiday_state="BY")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc, start=date(2024, 5, 1), end=date(2024, 5, 31))

        # Datum vor dem Block
        assert _resolve_location(student, date(2024, 4, 15)) is None
        # Datum nach dem Block
        assert _resolve_location(student, date(2024, 6, 15)) is None

    def test_returns_none_when_student_has_no_course(self, make_student):
        from absence.models import _resolve_location
        student = make_student()  # ohne Course
        assert _resolve_location(student, date(2024, 5, 15)) is None

    def test_returns_none_when_block_has_no_location(
        self, make_student, make_course, make_block
    ):
        from absence.models import _resolve_location
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=None, start=date(2024, 5, 1), end=date(2024, 5, 31))
        assert _resolve_location(student, date(2024, 5, 15)) is None


@pytest.mark.django_db
class TestResolveHolidayState:
    """`_resolve_holiday_state`: Standort > AbsenceSettings > ''."""

    def test_uses_location_state(
        self, make_student, make_course, make_location, make_block
    ):
        from absence.models import _resolve_holiday_state
        AbsenceSettings.objects.create(pk=1, holiday_state="BE")  # globaler Default
        loc_by = make_location("BY-Standort", holiday_state="BY")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc_by, start=date(2024, 5, 1), end=date(2024, 5, 31))

        # Standort-Bundesland gewinnt gegen globale Settings
        assert _resolve_holiday_state(student, date(2024, 5, 15)) == "BY"

    def test_falls_back_to_settings_when_location_state_empty(
        self, make_student, make_course, make_location, make_block
    ):
        from absence.models import _resolve_holiday_state
        AbsenceSettings.objects.create(pk=1, holiday_state="HE")
        loc = make_location("Standort ohne Bundesland", holiday_state="")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc, start=date(2024, 5, 1), end=date(2024, 5, 31))

        assert _resolve_holiday_state(student, date(2024, 5, 15)) == "HE"

    def test_falls_back_to_settings_when_no_block(self, make_student):
        from absence.models import _resolve_holiday_state
        AbsenceSettings.objects.create(pk=1, holiday_state="NW")
        student = make_student()
        assert _resolve_holiday_state(student, date(2024, 5, 15)) == "NW"


@pytest.mark.django_db
class TestVacationRequestLocationResolution:
    """End-to-End: VacationRequest mit echtem Standort → korrekte Feiertagslogik."""

    def test_uses_location_specific_holidays(
        self, make_student, make_course, make_location, make_block
    ):
        # 06.01.2025 ist Mo → Heilige Drei Könige (BY/BW/ST)
        loc_by = make_location("Bayern", holiday_state="BY")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc_by, start=date(2025, 1, 1), end=date(2025, 1, 31))

        # Urlaub Mo 06.01.–Fr 10.01.2025:
        # 5 Werktage minus 06.01. (Hl. Drei Könige in BY) = 4
        vr = VacationRequest(
            student=student,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 1, 10),
        )
        assert vr.duration_working_days == 4

    def test_berlin_does_not_subtract_heilige_drei_koenige(
        self, make_student, make_course, make_location, make_block
    ):
        loc_be = make_location("Berlin", holiday_state="BE")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc_be, start=date(2025, 1, 1), end=date(2025, 1, 31))

        # Urlaub Mo 06.01.–Fr 10.01.2025: 5 Werktage (06.01. nicht in BE)
        vr = VacationRequest(
            student=student,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 1, 10),
        )
        assert vr.duration_working_days == 5

    def test_location_override_wins_over_resolved(
        self, make_student, make_course, make_location, make_block
    ):
        loc_be = make_location("Berlin", holiday_state="BE")
        loc_by = make_location("Bayern", holiday_state="BY")
        course = make_course()
        student = make_student(course=course)
        # Auto-Resolver würde BE zurückgeben:
        make_block(course, location=loc_be, start=date(2025, 1, 1), end=date(2025, 1, 31))

        vr = VacationRequest.objects.create(
            student=student,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 1, 10),
            location_override=loc_by,  # manueller Override → BY
        )
        # Mit Override BY: 5 - 06.01. = 4 (statt 5 mit BE)
        assert vr.duration_working_days == 4
        assert vr.resolved_location == loc_by

    def test_resolved_location_falls_back_to_block(
        self, make_student, make_course, make_location, make_block
    ):
        loc = make_location("Auto-Standort", holiday_state="HE")
        course = make_course()
        student = make_student(course=course)
        make_block(course, location=loc, start=date(2024, 5, 1), end=date(2024, 5, 31))

        vr = VacationRequest.objects.create(
            student=student,
            start_date=date(2024, 5, 6),
            end_date=date(2024, 5, 10),
        )
        assert vr.resolved_location == loc
        assert vr.resolved_holiday_state == "HE"