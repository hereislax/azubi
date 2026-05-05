# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Formulare für Praxistutoren, Ausbildungskoordinationen und deren Mitglieder."""
from django import forms
from .models import Instructor, ChiefInstructor, TrainingCoordination


class InstructorForm(forms.ModelForm):
    """Formular zum Anlegen und Bearbeiten von Praxistutoren."""
    def __init__(self, *args, **kwargs):
        unit_queryset = kwargs.pop('unit_queryset', None)
        location_queryset = kwargs.pop('location_queryset', None)
        super().__init__(*args, **kwargs)
        if unit_queryset is not None:
            self.fields['unit'].queryset = unit_queryset
        if location_queryset is not None:
            self.fields['location'].queryset = location_queryset
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                pass
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    class Meta:
        model = Instructor
        fields = ['salutation', 'first_name', 'last_name', 'email', 'unit', 'location', 'job_profiles']
        widgets = {
            'job_profiles': forms.CheckboxSelectMultiple(),
        }


class TrainingCoordinationForm(forms.ModelForm):
    """Formular zum Anlegen und Bearbeiten von Ausbildungskoordinationen."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                pass
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    class Meta:
        model = TrainingCoordination
        fields = ['name', 'functional_email', 'units']
        widgets = {
            'units': forms.CheckboxSelectMultiple(),
        }

# Abwaertskompatibilitaet
KoordinationForm = TrainingCoordinationForm


class ChiefInstructorForm(forms.ModelForm):
    """Formular zum Anlegen und Bearbeiten von Mitgliedern einer Ausbildungskoordination."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    class Meta:
        model = ChiefInstructor
        fields = ['salutation', 'first_name', 'last_name', 'email', 'coordination']
