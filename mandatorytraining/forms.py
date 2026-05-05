# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Forms für Pflichtschulungen."""
from datetime import date

from django import forms

from .models import TrainingType, TrainingCompletion


class TrainingTypeForm(forms.ModelForm):
    """Schulungs-Typ anlegen/bearbeiten."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    class Meta:
        model = TrainingType
        fields = ['name', 'description', 'icon',
                  'recurrence', 'validity_months',
                  'fixed_deadline_month', 'fixed_deadline_day', 'fixed_recurrence_years',
                  'reminder_days_before',
                  'is_mandatory', 'applies_to_all_students', 'applies_to_job_profiles', 'active']
        widgets = {
            'description':              forms.Textarea(attrs={'rows': 2}),
            'applies_to_job_profiles':  forms.SelectMultiple(),
        }

    def clean(self):
        cleaned = super().clean()
        recurrence = cleaned.get('recurrence')
        if recurrence == 'fixed':
            if not cleaned.get('fixed_deadline_month') or not cleaned.get('fixed_deadline_day'):
                raise forms.ValidationError(
                    'Bei „Fester Stichtag" müssen Monat und Tag angegeben werden.',
                )
        return cleaned


class TrainingCompletionForm(forms.ModelForm):
    """Eine einzelne Teilnahme erfassen."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'kern-form-input__input')

    class Meta:
        model = TrainingCompletion
        fields = ['training_type', 'completed_on', 'expires_on', 'notes']
        widgets = {
            'completed_on': forms.DateInput(attrs={'type': 'date'}),
            'expires_on':   forms.DateInput(attrs={'type': 'date'}),
            'notes':        forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'expires_on': 'Leer lassen für Auto-Berechnung. Bei einmaligen Schulungen wird '
                          'das Feld ignoriert (lebenslang gültig).',
        }


class BulkCompletionForm(forms.Form):
    """Bulk-Erfassung: mehrere Azubis nach gemeinsamer Schulung markieren."""
    training_type = forms.ModelChoiceField(
        queryset=TrainingType.objects.filter(active=True).order_by('name'),
        label='Schulungs-Typ',
        widget=forms.Select(attrs={'class': 'kern-form-input__input'}),
    )
    completed_on = forms.DateField(
        label='Absolviert am',
        initial=date.today,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}),
    )
    expires_on_override = forms.DateField(
        label='Gültig bis (optional)',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}),
        help_text='Leer lassen für Auto-Berechnung anhand der Gültigkeitsdauer.',
    )
    students = forms.CharField(
        label='Teilnehmende Nachwuchskräfte (Komma-getrennte IDs)',
        required=True,
        widget=forms.HiddenInput(),
    )
    notes = forms.CharField(
        label='Anmerkung (optional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'kern-form-input__input'}),
    )

    def clean_students(self):
        raw = self.cleaned_data.get('students') or ''
        ids = [s.strip() for s in raw.split(',') if s.strip()]
        if not ids:
            raise forms.ValidationError('Bitte mindestens eine Nachwuchskraft auswählen.')
        return ids
