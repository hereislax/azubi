# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from datetime import date

from django import forms
from .models import VacationRequest, SickLeave, SICK_TYPE_CHOICES, HOLIDAY_STATE_CHOICES


class VacationRequestForm(forms.ModelForm):
    """Antragsformular für das Ausbildungsreferat (mit Standort-Override)."""
    class Meta:
        model = VacationRequest
        fields = ['student', 'start_date', 'end_date', 'notes', 'location_override']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date':   forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes':      forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'location_override': 'Standort (manuell überschreiben)',
        }
        help_texts = {
            'location_override': 'Optional. Wird normalerweise automatisch aus dem '
                                  'Ablaufplan ermittelt. Hier nur setzen wenn '
                                  'die automatische Zuordnung falsch ist.',
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end   = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('Das Enddatum darf nicht vor dem Startdatum liegen.')
        return cleaned


class VacationRequestPortalForm(forms.ModelForm):
    """Vereinfachtes Formular für das Nachwuchskräfte-Portal (ohne Student-Feld)."""
    class Meta:
        model = VacationRequest
        fields = ['start_date', 'end_date', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date':   forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes':      forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end   = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('Das Enddatum darf nicht vor dem Startdatum liegen.')
        return cleaned


class SickLeaveCreateForm(forms.ModelForm):
    class Meta:
        model = SickLeave
        fields = ['student', 'start_date', 'sick_type', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes':      forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('start_date') and not self.data.get('start_date'):
            self.fields['start_date'].initial = date.today()


class SickLeaveCloseForm(forms.Form):
    end_date = forms.DateField(
        label='Letzter Krankheitstag (Gesundgemeldet ab dem Folgetag)',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    notes = forms.CharField(
        label='Anmerkungen',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, sick_leave=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sick_leave = sick_leave

    def clean_end_date(self):
        end = self.cleaned_data['end_date']
        if self._sick_leave and end < self._sick_leave.start_date:
            raise forms.ValidationError(
                'Das Enddatum darf nicht vor dem ersten Krankheitstag liegen.'
            )
        return end


class AbsenceSettingsForm(forms.Form):
    vacation_office_email = forms.EmailField(
        label='E-Mail Urlaubsstelle',
        required=False,
        help_text='Täglich werden Urlaubsanträge und Krankmeldungen an diese Adresse gesendet.',
    )
    holiday_state = forms.ChoiceField(
        label='Bundesland (Feiertage)',
        choices=HOLIDAY_STATE_CHOICES,
        required=False,
        help_text='Bundesland für die Berechnung gesetzlicher Feiertage bei der Arbeitstagsermittlung.',
    )
