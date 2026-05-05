# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Aggregations-Service für die Kompetenzmatrix einer Nachwuchskraft.

Verbindet vier Datenquellen:

1. **Stationsbeurteilungen** (Fremd, ``assessment.Assessment`` + ``AssessmentRating``)
2. **Selbstbeurteilungen**   (Selbst, ``assessment.SelfAssessment`` + ``SelfAssessmentRating``)
3. **Kompetenz-Mapping**     (``CriterionCompetenceWeight`` — welches Kriterium auf welche Kompetenz)
4. **Curriculum-Coverage**   (`course.curriculum.get_curriculum_status` — welche Stationen sind erledigt)

Soll-Werte werden linear vom Kursstart (0) bis Kursende (CompetenceTarget.target_value)
interpoliert. Ist-Werte als gleitender Mittelwert der letzten N Beurteilungen pro Quelle.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal


# Beurteilungen werden durch dieses Skalen-Mapping in einen Skill-Wert (0–100) umgerechnet.
# - Notenskala 1,0–6,0  → 100 …   0   (linear, 1,0 = 100, 6,0 = 0)
# - Punkteskala 0–15    →   0 … 100   (linear)
def _grade_to_skill(value_str: str, scale: str) -> float | None:
    """Wandelt einen Bewertungswert (String) in einen Skill-Wert 0–100 um.

    Tolerant gegenüber „2,3" / „2.3" und Punkten als Dezimal/Komma.
    Liefert ``None`` bei Parsing-Fehlern.
    """
    if not value_str:
        return None
    try:
        v = float(value_str.replace(',', '.'))
    except (ValueError, AttributeError):
        return None
    if scale == 'grade':
        # 1,0 = 100; 6,0 = 0; linear dazwischen, geclamped
        v = max(1.0, min(6.0, v))
        return round((6.0 - v) / 5.0 * 100, 2)
    elif scale == 'points':
        v = max(0.0, min(15.0, v))
        return round(v / 15.0 * 100, 2)
    return None


def _moving_average(values: list[float], window: int = 3) -> float | None:
    """Gleitender Mittelwert der letzten ``window`` Werte (Default 3)."""
    if not values:
        return None
    tail = values[-window:]
    return round(sum(tail) / len(tail), 1)


def _interpolate_target(course_start: date | None, course_end: date | None,
                        target_value: float, today: date | None = None) -> float | None:
    """Linearer Soll-Wert vom Kursstart (0) bis Kursende (target_value) am ``today``."""
    if course_start is None or course_end is None or course_end <= course_start:
        return None
    if today is None:
        today = date.today()
    if today <= course_start:
        return 0.0
    if today >= course_end:
        return round(float(target_value), 1)
    total = (course_end - course_start).days
    elapsed = (today - course_start).days
    frac = elapsed / total
    return round(float(target_value) * frac, 1)


def get_competence_matrix(student, today: date | None = None, window: int = 3) -> dict:
    """Berechnet die Kompetenzmatrix für eine Nachwuchskraft.

    Returns:
        dict mit:
            apprentice_progress_pct (int)  — wie weit ist die Ausbildung zeitlich
            competences (list[dict])       — pro Kompetenz: aktuelle Werte, Soll, Verlauf
            month_columns (list[date])     — Monate seit Kursstart (für Heatmap)
            heatmap_rows (list[dict])      — pro Kompetenz: Werte je Monat (Self & External)
            no_data (bool)                 — True wenn keine Bewertungen / Targets vorhanden
    """
    from organisation.models import Competence
    from course.models import (
        CompetenceTarget, CurriculumRequirement, InternshipAssignment,
        ASSIGNMENT_STATUS_APPROVED,
    )
    from assessment.models import (
        Assessment, AssessmentRating, SelfAssessment, SelfAssessmentRating,
        STATUS_CONFIRMED, STATUS_SUBMITTED, CriterionCompetenceWeight,
    )

    today = today or date.today()
    course = getattr(student, 'course', None)
    job_profile = getattr(course, 'job_profile', None) if course else None
    course_start = getattr(course, 'start_date', None) if course else None
    course_end   = getattr(course, 'end_date',   None) if course else None

    # Ausbildungsfortschritt (zeitlich)
    apprentice_progress_pct = 0
    if course_start and course_end and course_end > course_start:
        clamped_today = max(course_start, min(today, course_end))
        apprentice_progress_pct = int(
            (clamped_today - course_start).days / (course_end - course_start).days * 100
        )

    if job_profile is None:
        return {
            'apprentice_progress_pct': 0,
            'competences': [],
            'month_columns': [],
            'heatmap_rows': [],
            'no_data': True,
        }

    # 1. Soll-Werte (CompetenceTarget) für dieses Berufsbild
    targets = {
        t.competence_id: t
        for t in CompetenceTarget.objects.filter(job_profile=job_profile).select_related('competence')
    }

    # 2. Mapping Kriterium → (Kompetenz, Gewicht)
    weights = list(
        CriterionCompetenceWeight.objects
        .filter(criterion__job_profile=job_profile)
        .select_related('criterion', 'competence')
    )
    weight_by_criterion: dict[int, list[tuple]] = {}
    for w in weights:
        weight_by_criterion.setdefault(w.criterion_id, []).append((w.competence, float(w.weight)))

    # Sammlung aller Kompetenzen, die irgendwie auftauchen (Soll oder Mapping)
    competence_ids: set[int] = set(targets.keys())
    for entries in weight_by_criterion.values():
        for c, _ in entries:
            competence_ids.add(c.pk)

    if not competence_ids:
        return {
            'apprentice_progress_pct': apprentice_progress_pct,
            'competences': [],
            'month_columns': [],
            'heatmap_rows': [],
            'no_data': True,
        }

    competences = {
        c.pk: c for c in Competence.objects.filter(pk__in=competence_ids)
    }

    # 3. Beurteilungs-Daten laden (nur für diese Nachwuchskraft)
    fremd_assessments = (
        Assessment.objects
        .filter(assignment__student=student, status=STATUS_CONFIRMED)
        .select_related('template', 'assignment')
        .prefetch_related('ratings__criterion')
        .order_by('assignment__end_date')
    )
    self_assessments = (
        SelfAssessment.objects
        .filter(assignment__student=student, status=STATUS_SUBMITTED)
        .select_related('template', 'assignment')
        .prefetch_related('ratings__criterion')
        .order_by('assignment__end_date')
    )

    # Pro Kompetenz: Liste (date, skill_value, source) für Verlauf
    history_external: dict[int, list[tuple[date, float]]] = {cid: [] for cid in competence_ids}
    history_self:     dict[int, list[tuple[date, float]]] = {cid: [] for cid in competence_ids}

    def _fold_assessment(assess, target_dict: dict):
        scale = assess.template.rating_scale
        # Pro Kompetenz: gewichteter Durchschnitt aus den passenden Kriterien dieser Beurteilung
        weighted_sum: dict[int, float] = {}
        weight_sum:   dict[int, float] = {}
        for r in assess.ratings.all():
            mapped = weight_by_criterion.get(r.criterion_id, [])
            if not mapped:
                continue
            skill = _grade_to_skill(r.value, scale)
            if skill is None:
                continue
            for comp, w in mapped:
                weighted_sum[comp.pk] = weighted_sum.get(comp.pk, 0.0) + skill * w
                weight_sum[comp.pk]   = weight_sum.get(comp.pk, 0.0) + w
        date_marker = assess.assignment.end_date or today
        for cid, ws in weighted_sum.items():
            if weight_sum.get(cid):
                target_dict.setdefault(cid, []).append((date_marker, ws / weight_sum[cid]))

    for a in fremd_assessments:
        _fold_assessment(a, history_external)
    for a in self_assessments:
        _fold_assessment(a, history_self)

    # 4. Curriculum-Coverage je Kompetenz (separat)
    cov_total: dict[int, int] = {}
    cov_done:  dict[int, int] = {}
    requirements = list(
        CurriculumRequirement.objects.filter(
            job_profile=job_profile, target_competence_id__in=competence_ids,
        )
    )
    if requirements:
        approved_assignments = list(
            InternshipAssignment.objects
            .filter(student=student, status=ASSIGNMENT_STATUS_APPROVED)
            .select_related('unit')
            .prefetch_related('unit__competences')
        )
        for req in requirements:
            cid = req.target_competence_id
            cov_total[cid] = cov_total.get(cid, 0) + 1
            req_target_unit_pks = set(req.target_units.values_list('pk', flat=True))
            for a in approved_assignments:
                matched = (
                    a.unit_id in req_target_unit_pks
                    if req_target_unit_pks
                    else a.unit.competences.filter(pk=cid).exists()
                )
                if matched and (a.end_date - a.start_date).days + 1 >= req.min_duration_weeks * 7:
                    cov_done[cid] = cov_done.get(cid, 0) + 1
                    break

    # Aufbau der Kompetenz-Liste
    competence_rows = []
    for cid in sorted(competence_ids, key=lambda i: competences[i].name.lower()):
        comp = competences[cid]
        ext_values = [v for _, v in history_external.get(cid, [])]
        self_values = [v for _, v in history_self.get(cid, [])]

        target = targets.get(cid)
        target_now = (
            _interpolate_target(course_start, course_end, float(target.target_value), today)
            if target else None
        )

        coverage_pct = None
        if cid in cov_total and cov_total[cid]:
            coverage_pct = round(cov_done.get(cid, 0) / cov_total[cid] * 100)

        competence_rows.append({
            'competence':       comp,
            'external_value':   _moving_average(ext_values,  window),
            'self_value':       _moving_average(self_values, window),
            'target_now':       target_now,
            'target_end':       float(target.target_value) if target else None,
            'history_external': history_external.get(cid, []),
            'history_self':     history_self.get(cid, []),
            'coverage_pct':     coverage_pct,
        })

    # 5. Heatmap-Daten: Monatsspalten vom Kursstart bis heute (max. aktueller Monat)
    month_columns: list[date] = []
    if course_start:
        m = date(course_start.year, course_start.month, 1)
        last_month = date(today.year, today.month, 1)
        while m <= last_month:
            month_columns.append(m)
            # zum nächsten Monat
            if m.month == 12:
                m = date(m.year + 1, 1, 1)
            else:
                m = date(m.year, m.month + 1, 1)

    def _month_aggregate(history: list[tuple[date, float]], month_start: date, month_end: date) -> float | None:
        vals = [v for d, v in history if month_start <= d <= month_end]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 1)

    heatmap_rows = []
    for row in competence_rows:
        ext_cells = []
        self_cells = []
        for i, m_start in enumerate(month_columns):
            if i + 1 < len(month_columns):
                m_end = month_columns[i + 1] - timedelta(days=1)
            else:
                m_end = today
            ext_cells.append(_month_aggregate(row['history_external'], m_start, m_end))
            self_cells.append(_month_aggregate(row['history_self'], m_start, m_end))
        heatmap_rows.append({
            'competence': row['competence'],
            'external':   ext_cells,
            'self':       self_cells,
        })

    return {
        'apprentice_progress_pct': apprentice_progress_pct,
        'competences':             competence_rows,
        'month_columns':           month_columns,
        'heatmap_rows':            heatmap_rows,
        'no_data':                 not (history_external or history_self) and not targets,
    }