# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Automatische Vorschläge für Praktikumseinsätze."""
from datetime import date

from organisation.models import OrganisationalUnit
from .models import (
    InternshipAssignment, CurriculumRequirement, ASSIGNMENT_STATUS_APPROVED,
)


def generate_suggestions(student, schedule_block, full_unit_pks=None):
    """
    Generiert Vorschläge für Praktikumseinsätze einer Nachwuchskraft.

    Ranking-Kriterien (absteigend nach Gewicht):
      1. Erfüllt offene Curriculum-Anforderung (Kompetenz oder spezifische OE)
      2. Passt zu NK-Wunsch (Abteilung/Behörde oder Standort)
      3. Hat freie Kapazität
      4. Wurde noch nicht besucht

    Returns:
        list[dict] mit Keys:
            unit, score, reasons (list[str]),
            curriculum_match (str|None), capacity_info (str),
            is_preferred (bool)
    """
    if full_unit_pks is None:
        full_unit_pks = set()

    try:
        job_profile = student.course.job_profile
    except AttributeError:
        job_profile = None

    # Alle aktiven OEs als Kandidaten (nur Blatt-Ebenen: Referat + Sachgebiet)
    candidate_units = list(
        OrganisationalUnit.objects
        .filter(is_active=True, unit_type__in=['division', 'section'])
        .prefetch_related('competences', 'locations')
    )

    # Bereits besuchte OEs (approved assignments)
    visited_unit_ids = set(
        InternshipAssignment.objects
        .filter(student=student, status=ASSIGNMENT_STATUS_APPROVED)
        .values_list('unit_id', flat=True)
    )

    # Offene Curriculum-Anforderungen
    open_requirements = []
    if job_profile:
        from .curriculum import get_curriculum_status
        curriculum = get_curriculum_status(student)
        open_requirements = [
            item for item in curriculum
            if item['status'] in ('missing', 'in_progress') and item['requirement'].is_mandatory
        ]

    # Vorberechnungen: welche OE erfüllt welche Anforderung?
    req_by_competence = {}   # competence_pk → requirement
    req_by_unit = {}         # unit_pk → requirement
    for item in open_requirements:
        req = item['requirement']
        target_pks = set(req.target_units.values_list('pk', flat=True))
        if target_pks:
            for pk in target_pks:
                req_by_unit[pk] = req
        elif req.target_competence_id:
            req_by_competence[req.target_competence_id] = req

    # NK-Präferenzen laden
    preferred_unit_ids = set()
    preferred_location_ids = set()
    preferred_ancestor_ids = set()
    try:
        pref = student.internship_preference
        preferred_unit_ids = set(pref.preferred_units.values_list('pk', flat=True))
        preferred_location_ids = set(pref.preferred_locations.values_list('pk', flat=True))
        # Gewünschte Abteilungen/Behörden → alle Nachkommen finden
        if preferred_unit_ids:
            all_units = list(OrganisationalUnit.objects.only('pk', 'parent_id'))
            children_map = {}
            for u in all_units:
                if u.parent_id:
                    children_map.setdefault(u.parent_id, []).append(u.pk)

            def _descendants(pk):
                result = {pk}
                for child_pk in children_map.get(pk, []):
                    result |= _descendants(child_pk)
                return result

            for uid in preferred_unit_ids:
                preferred_ancestor_ids |= _descendants(uid)
    except Exception:
        pass

    # Scoring
    suggestions = []
    for unit in candidate_units:
        if unit.pk in full_unit_pks:
            continue  # Kein Platz

        score = 0
        reasons = []
        curriculum_match = None
        is_preferred = False

        # 1. Curriculum-Match (höchstes Gewicht)
        matched_req = req_by_unit.get(unit.pk)
        if not matched_req:
            unit_competence_ids = set(unit.competences.values_list('pk', flat=True))
            for comp_id in unit_competence_ids:
                if comp_id in req_by_competence:
                    matched_req = req_by_competence[comp_id]
                    break

        if matched_req:
            score += 100
            curriculum_match = matched_req.name
            reasons.append(f'Erfüllt Anforderung „{matched_req.name}"')

        # 2. NK-Wunsch: Abteilung/Behörde
        if unit.pk in preferred_ancestor_ids:
            score += 35
            is_preferred = True
            reasons.append('Gewünschte Abteilung/Behörde')

        # 3. NK-Wunsch: Standort
        unit_location_ids = set(unit.locations.values_list('pk', flat=True))
        if preferred_location_ids & unit_location_ids:
            score += 75
            is_preferred = True
            reasons.append('Gewünschter Standort')

        # 4. Bereits besucht → nicht vorschlagen
        if unit.pk in visited_unit_ids:
            continue

        # Nur relevante Vorschläge (mindestens ein positiver Grund)
        if score <= 0:
            continue

        suggestions.append({
            'unit': unit,
            'score': score,
            'reasons': reasons,
            'curriculum_match': curriculum_match,
            'is_preferred': is_preferred,
        })

    # Sortieren: höchster Score zuerst
    suggestions.sort(key=lambda s: s['score'], reverse=True)

    return suggestions[:15]  # Top 15
