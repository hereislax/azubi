# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Formulare zum Stellen von Änderungsanträgen für Praktikumseinsätze.

Pro Änderungstyp gibt es ein eigenes Formular, das die typabhängigen
Eingaben validiert und einen JSON-Payload für ``AssignmentChangeRequest``
erzeugt.
"""
from django import forms

from .models import (
    CHANGE_TYPE_CANCEL,
    CHANGE_TYPE_INSTRUCTOR,
    CHANGE_TYPE_LOCATION,
    CHANGE_TYPE_SHIFT,
    CHANGE_TYPE_SPLIT,
    CHANGE_TYPE_UNIT_CHANGE,
)


_INPUT_CLASS = 'kern-form-input__input'


def _style(field: forms.Field) -> None:
    """Setzt den projektweiten KERN-Input-Style auf das Feld."""
    field.widget.attrs.setdefault('class', _INPUT_CLASS)


class _BaseChangeRequestForm(forms.Form):
    """Basisklasse: kennt das ``InternshipAssignment`` und liefert einen Payload."""
    change_type: str = ''

    reason = forms.CharField(
        label='Begründung',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        for field in self.fields.values():
            _style(field)

    def get_payload(self) -> dict:
        raise NotImplementedError


class SplitChangeRequestForm(_BaseChangeRequestForm):
    change_type = CHANGE_TYPE_SPLIT

    split_date = forms.DateField(
        label='Teilungsdatum',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    def clean_split_date(self):
        d = self.cleaned_data['split_date']
        a = self.assignment
        if not (a.start_date < d < a.end_date):
            raise forms.ValidationError(
                'Das Teilungsdatum muss zwischen Beginn und Ende des Einsatzes liegen.'
            )
        return d

    def get_payload(self) -> dict:
        return {'split_date': self.cleaned_data['split_date'].isoformat()}


class ShiftChangeRequestForm(_BaseChangeRequestForm):
    change_type = CHANGE_TYPE_SHIFT

    new_start_date = forms.DateField(
        label='Neues Startdatum',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    new_end_date = forms.DateField(
        label='Neues Enddatum',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    def clean(self):
        cleaned = super().clean()
        s, e = cleaned.get('new_start_date'), cleaned.get('new_end_date')
        if s and e and e < s:
            raise forms.ValidationError('Das neue Enddatum darf nicht vor dem neuen Startdatum liegen.')
        return cleaned

    def get_payload(self) -> dict:
        return {
            'new_start_date': self.cleaned_data['new_start_date'].isoformat(),
            'new_end_date':   self.cleaned_data['new_end_date'].isoformat(),
        }


class UnitChangeRequestForm(_BaseChangeRequestForm):
    change_type = CHANGE_TYPE_UNIT_CHANGE

    new_unit = forms.ModelChoiceField(
        label='Neue Organisationseinheit',
        queryset=None,
    )

    def __init__(self, *args, unit_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        from organisation.models import OrganisationalUnit
        if unit_queryset is None:
            unit_queryset = OrganisationalUnit.objects.filter(is_active=True)
        self.fields['new_unit'].queryset = (
            unit_queryset.exclude(pk=self.assignment.unit_id).order_by('unit_type', 'name')
        )

    def get_payload(self) -> dict:
        return {'new_unit_id': self.cleaned_data['new_unit'].pk}


class LocationChangeRequestForm(_BaseChangeRequestForm):
    change_type = CHANGE_TYPE_LOCATION

    new_location = forms.ModelChoiceField(
        label='Neuer Standort',
        queryset=None,
    )

    def __init__(self, *args, location_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        from organisation.models import Location
        qs = location_queryset if location_queryset is not None else Location.objects.all()
        qs = qs.order_by('name')
        if self.assignment.location_id:
            qs = qs.exclude(pk=self.assignment.location_id)
        self.fields['new_location'].queryset = qs

    def get_payload(self) -> dict:
        return {'new_location_id': self.cleaned_data['new_location'].pk}


class InstructorChangeRequestForm(_BaseChangeRequestForm):
    """Praxistutor-Wechsel — wird ohne Genehmigung sofort wirksam."""
    change_type = CHANGE_TYPE_INSTRUCTOR

    new_instructor = forms.ModelChoiceField(
        label='Neuer Praxistutor',
        queryset=None,
        required=False,
        empty_label='– kein Praxistutor –',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from instructor.models import Instructor
        qs = Instructor.objects.all().order_by('last_name', 'first_name')
        if self.assignment.unit_id:
            qs = qs.filter(unit_id=self.assignment.unit_id)
        self.fields['new_instructor'].queryset = qs

    def get_payload(self) -> dict:
        ins = self.cleaned_data.get('new_instructor')
        return {'new_instructor_id': ins.pk if ins else None}


class CancelChangeRequestForm(_BaseChangeRequestForm):
    change_type = CHANGE_TYPE_CANCEL

    confirm = forms.BooleanField(
        label='Ich möchte diesen Einsatz wirklich stornieren.',
        required=True,
    )

    def get_payload(self) -> dict:
        return {}


FORM_BY_TYPE = {
    CHANGE_TYPE_SPLIT:       SplitChangeRequestForm,
    CHANGE_TYPE_SHIFT:       ShiftChangeRequestForm,
    CHANGE_TYPE_UNIT_CHANGE: UnitChangeRequestForm,
    CHANGE_TYPE_INSTRUCTOR:  InstructorChangeRequestForm,
    CHANGE_TYPE_LOCATION:    LocationChangeRequestForm,
    CHANGE_TYPE_CANCEL:      CancelChangeRequestForm,
}


def get_form_class(change_type: str):
    return FORM_BY_TYPE.get(change_type)
