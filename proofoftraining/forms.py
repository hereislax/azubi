# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import forms
from django.forms import inlineformset_factory

from .models import TrainingRecord, TrainingDay


class TrainingRecordCreateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['week_start'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}, format='%Y-%m-%d')
        self.fields['week_start'].input_formats = ['%Y-%m-%d']
        self.fields['week_start'].help_text = 'Bitte den Montag der betreffenden Woche auswählen.'

    def clean_week_start(self):
        d = self.cleaned_data.get('week_start')
        if d and d.weekday() != 0:
            raise forms.ValidationError('Bitte wählen Sie den Montag der Woche (nicht einen anderen Wochentag).')
        return d

    class Meta:
        model = TrainingRecord
        fields = ['week_start']


class TrainingDayForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        day = self.instance
        day_label = ''
        if day and getattr(day, 'date', None):
            day_label = f"{day.weekday_name}, {day.date.strftime('%d.%m.%Y')}"
        self.fields['day_type'].widget.attrs['class'] = 'kern-form-input__input'
        self.fields['day_type'].widget.attrs['aria-label'] = (
            f"Tagtyp für {day_label}" if day_label else 'Tagtyp'
        )
        self.fields['content'].widget = forms.Textarea(attrs={
            'rows': 3,
            'class': 'kern-form-input__input',
            'placeholder': 'Beschreibung der Tätigkeiten oder gelernten Inhalte …',
            'aria-label': (f"Tätigkeiten am {day_label}" if day_label else 'Tätigkeiten'),
        })
        self.fields['content'].required = False

    class Meta:
        model = TrainingDay
        fields = ['day_type', 'content']


TrainingDayFormSet = inlineformset_factory(
    TrainingRecord,
    TrainingDay,
    form=TrainingDayForm,
    extra=0,
    can_delete=False,
)


class RejectForm(forms.Form):
    rejection_reason = forms.CharField(
        label='Korrekturhinweis',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'kern-form-input__input',
                                     'placeholder': 'Bitte beschreiben Sie, was korrigiert werden soll …'}),
        required=True,
    )
