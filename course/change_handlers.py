# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Anwendungs-Logik für ``AssignmentChangeRequest`` je Änderungstyp.

Jeder Handler nimmt einen genehmigten ``AssignmentChangeRequest`` entgegen und
modifiziert den zugehörigen ``InternshipAssignment`` entsprechend dem Payload.
Bei jeder strukturellen Änderung außer einer Stornierung wird der Einsatzstatus
auf ``pending`` zurückgesetzt – Änderungen bedürfen der erneuten Bestätigung
durch die Ausbildungskoordination.
"""
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction


def _parse_date(value, field: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError as exc:
            raise ValidationError({field: 'Ungültiges Datumsformat (erwartet: YYYY-MM-DD).'}) from exc
    raise ValidationError({field: 'Datum fehlt.'})


def _reset_to_pending(assignment, *, fields_changed):
    from course.models import ASSIGNMENT_STATUS_PENDING
    update_fields = list(fields_changed) + ['status', 'rejection_reason']
    assignment.status = ASSIGNMENT_STATUS_PENDING
    assignment.rejection_reason = ''
    assignment.save(update_fields=update_fields)
    assignment.bump_notification_sequence()


@transaction.atomic
def _apply_split(change_request, *, decided_by):
    from course.models import InternshipAssignment, ASSIGNMENT_STATUS_PENDING

    a = change_request.assignment
    split_date = _parse_date(change_request.payload.get('split_date'), 'split_date')
    if not (a.start_date < split_date < a.end_date):
        raise ValidationError('Das Teilungsdatum muss zwischen Beginn und Ende des Einsatzes liegen.')

    original_end = a.end_date
    second_start = split_date + timedelta(days=1)

    a.end_date = split_date
    a.status = ASSIGNMENT_STATUS_PENDING
    a.rejection_reason = ''
    a.save(update_fields=['end_date', 'status', 'rejection_reason'])
    a.bump_notification_sequence()

    second = InternshipAssignment.objects.create(
        schedule_block=a.schedule_block,
        student=a.student,
        unit=a.unit,
        start_date=second_start,
        end_date=original_end,
        instructor=a.instructor,
        location=a.location,
        notes=a.notes,
        created_by=decided_by,
    )
    from course.workflow_helpers import start_assignment_workflow
    start_assignment_workflow(second, initiator=decided_by)


@transaction.atomic
def _apply_shift(change_request, *, decided_by):
    a = change_request.assignment
    p = change_request.payload or {}
    new_start = _parse_date(p.get('new_start_date'), 'new_start_date')
    new_end   = _parse_date(p.get('new_end_date'),   'new_end_date')
    if new_end < new_start:
        raise ValidationError('Das neue Enddatum darf nicht vor dem neuen Startdatum liegen.')

    a.start_date = new_start
    a.end_date = new_end
    _reset_to_pending(a, fields_changed=['start_date', 'end_date'])


@transaction.atomic
def _apply_unit_change(change_request, *, decided_by):
    from organisation.models import OrganisationalUnit
    a = change_request.assignment
    new_unit_id = (change_request.payload or {}).get('new_unit_id')
    if not new_unit_id:
        raise ValidationError({'new_unit_id': 'Neue Organisationseinheit fehlt.'})
    try:
        new_unit = OrganisationalUnit.objects.get(pk=new_unit_id)
    except OrganisationalUnit.DoesNotExist as exc:
        raise ValidationError({'new_unit_id': 'Organisationseinheit existiert nicht.'}) from exc

    a.unit = new_unit
    _reset_to_pending(a, fields_changed=['unit'])


@transaction.atomic
def _apply_instructor(change_request, *, decided_by):
    """Praxistutor-Wechsel: keine erneute Genehmigung des Einsatzes nötig."""
    from instructor.models import Instructor
    a = change_request.assignment
    new_instructor_id = (change_request.payload or {}).get('new_instructor_id')

    if new_instructor_id:
        try:
            a.instructor = Instructor.objects.get(pk=new_instructor_id)
        except Instructor.DoesNotExist as exc:
            raise ValidationError({'new_instructor_id': 'Praxistutor existiert nicht.'}) from exc
    else:
        a.instructor = None

    a.save(update_fields=['instructor'])
    a.bump_notification_sequence()


@transaction.atomic
def _apply_location(change_request, *, decided_by):
    from organisation.models import Location
    a = change_request.assignment
    new_location_id = (change_request.payload or {}).get('new_location_id')
    if not new_location_id:
        raise ValidationError({'new_location_id': 'Neuer Standort fehlt.'})
    try:
        new_location = Location.objects.get(pk=new_location_id)
    except Location.DoesNotExist as exc:
        raise ValidationError({'new_location_id': 'Standort existiert nicht.'}) from exc

    a.location = new_location
    _reset_to_pending(a, fields_changed=['location'])


@transaction.atomic
def _apply_cancel(change_request, *, decided_by):
    change_request.assignment.delete()


_HANDLERS = {
    'split':       _apply_split,
    'shift':       _apply_shift,
    'unit_change': _apply_unit_change,
    'instructor':  _apply_instructor,
    'location':    _apply_location,
    'cancel':      _apply_cancel,
}


def apply_change_request(change_request, *, decided_by):
    """Wendet die im ``change_request`` beantragte Änderung an."""
    handler = _HANDLERS.get(change_request.change_type)
    if handler is None:
        raise ValidationError(f'Unbekannter Änderungstyp: {change_request.change_type}')
    handler(change_request, decided_by=decided_by)
