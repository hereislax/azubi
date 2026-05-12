# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Formulare für das Beurteilungssystem.

AssessmentTokenForm  – für Praxistutoren (öffentlich, kein Login)
SelfAssessmentForm   – für Auszubildende im Portal
"""
from django import forms
from .models import (
    Assessment, AssessmentRating, AssessmentTemplateCriterion,
    SelfAssessment, SelfAssessmentRating,
    StationFeedback, StationFeedbackRating, StationFeedbackCategory,
    SCALE_GRADE, SCALE_POINTS, GRADE_VALUES,
    STATUS_SUBMITTED,
)

# Gültige Noten für die Radio-Darstellung
GRADE_CHOICES = [(v, v) for v in GRADE_VALUES]


def _build_rating_fields(template, prefix='criterion'):
    """
    Erstellt dynamische Formularfelder für jedes Kriterium der Vorlage.
    Gibt ein OrderedDict zurück: {field_name: field}.
    """
    fields = {}
    tc_qs = (
        AssessmentTemplateCriterion.objects
        .filter(template=template)
        .select_related('criterion')
        .order_by('order')
    )
    for tc in tc_qs:
        field_name = f'{prefix}_{tc.criterion.pk}'
        comment_name = f'comment_{tc.criterion.pk}'

        if template.rating_scale == SCALE_GRADE:
            fields[field_name] = forms.ChoiceField(
                label=tc.criterion.name,
                choices=GRADE_CHOICES,
                widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                required=True,
                help_text=tc.criterion.help_text or '',
            )
        else:  # SCALE_POINTS
            fields[field_name] = forms.IntegerField(
                label=tc.criterion.name,
                min_value=0,
                max_value=15,
                required=True,
                help_text=tc.criterion.help_text or '',
                widget=forms.NumberInput(attrs={
                    'class': 'kern-form-input__input',
                    'style': 'width:100px',
                    'aria-describedby': 'rating-scale-hint',
                    'aria-required': 'true',
                    'inputmode': 'numeric',
                }),
            )

        fields[comment_name] = forms.CharField(
            label='Kommentar',
            required=False,
            widget=forms.Textarea(attrs={
                'class': 'kern-form-input__input',
                'rows': 2,
                'aria-label': f'Kommentar zu „{tc.criterion.name}"',
            }),
        )
    return fields


class AssessmentTokenForm(forms.Form):
    """Beurteilungsformular für Praxistutoren (tokenbasierter Zugang, kein Login)."""

    overall_comment = forms.CharField(
        label='Gesamtkommentar / Anmerkungen',
        required=False,
        widget=forms.Textarea(attrs={'class': 'kern-form-input__input', 'rows': 4}),
    )

    def __init__(self, assessment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.assessment = assessment
        self.template = assessment.template

        # Dynamische Kriterienfelder vor overall_comment einfügen
        rating_fields = _build_rating_fields(self.template, prefix='criterion')
        # Django-Formulare sind geordnet – Kriterien zuerst
        new_fields = {**rating_fields, 'overall_comment': self.fields['overall_comment']}
        self.fields = new_fields

    def get_criterion_pairs(self):
        """Iterator über (tc, rating_field, comment_field) für Template-Rendering."""
        tc_qs = (
            AssessmentTemplateCriterion.objects
            .filter(template=self.template)
            .select_related('criterion')
            .order_by('order')
        )
        for tc in tc_qs:
            yield (
                tc,
                self[f'criterion_{tc.criterion.pk}'],
                self[f'comment_{tc.criterion.pk}'],
            )

    def save(self):
        """Speichert Ratings und setzt Status auf SUBMITTED."""
        from django.utils import timezone

        assessment = self.assessment
        tc_qs = (
            AssessmentTemplateCriterion.objects
            .filter(template=self.template)
            .select_related('criterion')
            .order_by('order')
        )
        for tc in tc_qs:
            value   = str(self.cleaned_data.get(f'criterion_{tc.criterion.pk}', ''))
            comment = self.cleaned_data.get(f'comment_{tc.criterion.pk}', '')
            AssessmentRating.objects.update_or_create(
                assessment=assessment,
                criterion=tc.criterion,
                defaults={'value': value, 'comment': comment},
            )

        assessment.overall_comment = self.cleaned_data.get('overall_comment', '')
        assessment.status = STATUS_SUBMITTED
        assessment.submitted_at = timezone.now()
        assessment.save(update_fields=['overall_comment', 'status', 'submitted_at'])
        return assessment


STATION_GRADE_CHOICES = [
    ('1', '1 – sehr gut'),
    ('2', '2 – gut'),
    ('3', '3 – befriedigend'),
    ('4', '4 – ausreichend'),
    ('5', '5 – mangelhaft'),
    ('6', '6 – ungenügend'),
]


class StationFeedbackForm(forms.Form):
    """
    Anonymes Stationsbewertungsformular für Nachwuchskräfte.
    Für jede aktive StationFeedbackCategory wird ein RadioSelect-Feld (Note 1–6) erzeugt.
    """

    comment = forms.CharField(
        label='Anmerkungen (optional)',
        required=False,
        widget=forms.Textarea(attrs={'class': 'kern-form-input__input', 'rows': 3,
                                     'placeholder': 'Hier können Sie optional einen allgemeinen Kommentar hinterlassen.'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = StationFeedbackCategory.objects.filter(active=True).order_by('order', 'name')
        rating_fields = {}
        for cat in categories:
            field_name = f'category_{cat.pk}'
            rating_fields[field_name] = forms.ChoiceField(
                label=cat.label,
                choices=STATION_GRADE_CHOICES,
                widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                required=True,
                help_text=cat.help_text or '',
            )
        # Kategorie-Felder zuerst, Kommentar am Ende
        self.fields = {**rating_fields, 'comment': self.fields['comment']}

    def get_category_pairs(self):
        """Iterator über (category, bound_field) für Template-Rendering."""
        categories = StationFeedbackCategory.objects.filter(active=True).order_by('order', 'name')
        for cat in categories:
            yield cat, self[f'category_{cat.pk}']

    def save(self, assignment):
        """
        Erstellt StationFeedback + StationFeedbackRating-Objekte (anonym, kein Student-FK).
        Setzt assignment.station_feedback_submitted = True.
        """
        feedback = StationFeedback.objects.create(
            unit=assignment.unit,
            schedule_block=assignment.schedule_block,
            comment=self.cleaned_data.get('comment', ''),
        )
        categories = StationFeedbackCategory.objects.filter(active=True)
        for cat in categories:
            value_str = self.cleaned_data.get(f'category_{cat.pk}')
            if value_str:
                StationFeedbackRating.objects.create(
                    feedback=feedback,
                    category=cat,
                    value=int(value_str),
                )
        assignment.station_feedback_submitted = True
        assignment.save(update_fields=['station_feedback_submitted'])
        return feedback


class SelfAssessmentForm(forms.Form):
    """Selbstbeurteilungsformular für Auszubildende im Portal."""

    overall_comment = forms.CharField(
        label='Gesamtkommentar / Anmerkungen',
        required=False,
        widget=forms.Textarea(attrs={'class': 'kern-form-input__input', 'rows': 4}),
    )

    def __init__(self, self_assessment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.self_assessment = self_assessment
        self.template = self_assessment.template

        rating_fields = _build_rating_fields(self.template, prefix='criterion')
        self.fields = {**rating_fields, 'overall_comment': self.fields['overall_comment']}

        # Vorhandene Werte vorausfüllen
        for rating in self_assessment.ratings.select_related('criterion'):
            field_key = f'criterion_{rating.criterion.pk}'
            comment_key = f'comment_{rating.criterion.pk}'
            if field_key in self.fields:
                self.fields[field_key].initial = rating.value
            if comment_key in self.fields:
                self.fields[comment_key].initial = rating.comment
        self.fields['overall_comment'].initial = self_assessment.overall_comment

    def get_criterion_pairs(self):
        tc_qs = (
            AssessmentTemplateCriterion.objects
            .filter(template=self.template)
            .select_related('criterion')
            .order_by('order')
        )
        for tc in tc_qs:
            yield (
                tc,
                self[f'criterion_{tc.criterion.pk}'],
                self[f'comment_{tc.criterion.pk}'],
            )

    def save(self, submit=False):
        """Speichert den Entwurf oder reicht ein (submit=True)."""
        from django.utils import timezone

        sa = self.self_assessment
        tc_qs = (
            AssessmentTemplateCriterion.objects
            .filter(template=self.template)
            .select_related('criterion')
            .order_by('order')
        )
        for tc in tc_qs:
            value   = str(self.cleaned_data.get(f'criterion_{tc.criterion.pk}', ''))
            comment = self.cleaned_data.get(f'comment_{tc.criterion.pk}', '')
            SelfAssessmentRating.objects.update_or_create(
                self_assessment=sa,
                criterion=tc.criterion,
                defaults={'value': value, 'comment': comment},
            )

        sa.overall_comment = self.cleaned_data.get('overall_comment', '')
        if submit:
            sa.status = STATUS_SUBMITTED
            sa.submitted_at = timezone.now()
            sa.save(update_fields=['overall_comment', 'status', 'submitted_at'])
        else:
            sa.save(update_fields=['overall_comment'])
        return sa


class AssessmentCriterionForm(forms.ModelForm):
    """Form für Beurteilungskriterium (ohne Kompetenz-Mapping; das läuft separat als FormSet)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "kern-form-input__input")

    class Meta:
        from .models import AssessmentCriterion
        model = AssessmentCriterion
        fields = ['name', 'category', 'order', 'help_text']
        widgets = {
            'help_text': forms.Textarea(attrs={'rows': 2}),
        }


class CompetenceTargetForm(forms.ModelForm):
    """Form für Kompetenz-Endziel pro Berufsbild."""
    def __init__(self, *args, job_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "kern-form-input__input")
        if job_profile:
            # nur Kompetenzen anzeigen, die noch kein Endziel für dieses Berufsbild haben
            from organisation.models import Competence
            from course.models import CompetenceTarget
            existing_pks = CompetenceTarget.objects.filter(
                job_profile=job_profile,
            ).exclude(pk=getattr(self.instance, 'pk', None)).values_list('competence_id', flat=True)
            self.fields['competence'].queryset = Competence.objects.exclude(
                pk__in=existing_pks
            ).order_by('name')

    class Meta:
        from course.models import CompetenceTarget
        model = CompetenceTarget
        fields = ['competence', 'target_value']
