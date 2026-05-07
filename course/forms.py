# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import forms
from .models import Course, ScheduleBlock, InternshipAssignment, SeminarLecture


class CourseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError("Das Enddatum muss nach dem Startdatum liegen.")
        return cleaned_data

    class Meta:
        model = Course
        fields = ['title', 'start_date', 'end_date', 'job_profile']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }


class ScheduleBlockForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self._course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'kern-form-check__checkbox')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end:
            if end <= start:
                raise forms.ValidationError("Das Enddatum muss nach dem Startdatum liegen.")
            if self._course:
                qs = ScheduleBlock.objects.filter(
                    course=self._course,
                    start_date__lt=end,
                    end_date__gt=start,
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    conflicting = qs.first()
                    raise forms.ValidationError(
                        f'Dieser Zeitraum überschneidet sich mit „{conflicting.name}" '
                        f'({conflicting.start_date.strftime("%d.%m.%Y")} – {conflicting.end_date.strftime("%d.%m.%Y")}).'
                    )
        return cleaned_data

    class Meta:
        model = ScheduleBlock
        fields = ['name', 'block_type', 'location', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }


class InternshipAssignmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self._block = kwargs.pop('block', None)
        self._course = kwargs.pop('course', None)
        self._full_unit_pks = kwargs.pop('full_unit_pks', set())
        unit_queryset = kwargs.pop('unit_queryset', None)
        readonly_dates = kwargs.pop('readonly_dates', False)
        location_readonly = kwargs.pop('location_readonly', False)
        student_readonly = kwargs.pop('student_readonly', False)
        unit_readonly = kwargs.pop('unit_readonly', False)
        self._student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        if readonly_dates:
            self.fields['start_date'].disabled = True
            self.fields['end_date'].disabled = True
        if unit_readonly:
            self.fields['unit'].disabled = True
        if self._course:
            from student.models import Student
            self.fields['student'].queryset = (
                Student.objects.filter(course=self._course)
                .select_related('gender')
                .order_by('last_name', 'first_name')
            )
        from organisation.models import OrganisationalUnit
        if unit_queryset is not None:
            self.fields['unit'].queryset = unit_queryset
        else:
            self.fields['unit'].queryset = OrganisationalUnit.objects.filter(is_active=True).order_by('unit_type', 'name')
        # Praxistutor-Queryset: nach aktueller Einheit und – falls vorhanden – Berufsbild der Nachwuchskraft filtern
        from instructor.models import Instructor, INSTRUCTOR_STATUS_CONFIRMED
        instructor_qs = Instructor.objects.filter(status=INSTRUCTOR_STATUS_CONFIRMED).select_related('salutation').order_by('last_name', 'first_name')
        current_unit = None
        if self.instance and self.instance.pk:
            current_unit = self.instance.unit_id
        if current_unit:
            instructor_qs = instructor_qs.filter(unit_id=current_unit)
            student = self._student or (self.instance.student if self.instance and self.instance.pk else None)
            if student and student.course and student.course.job_profile_id:
                instructor_qs = instructor_qs.filter(job_profiles=student.course.job_profile_id)
        self.fields['instructor'].queryset = instructor_qs
        from organisation.models import Location, OrganisationalUnit
        # Standort-Queryset: basierend auf der OE (gespeichert oder aus POST/initial)
        unit_id = None
        if self.instance and self.instance.pk and self.instance.unit_id:
            unit_id = self.instance.unit_id
        elif self.data.get('unit'):
            unit_id = self.data.get('unit')
        elif self.initial.get('unit'):
            unit_id = self.initial.get('unit')

        if unit_id:
            unit = OrganisationalUnit.objects.filter(pk=unit_id).first()
            if unit:
                loc_pks = list(unit.get_all_locations().values_list('pk', flat=True))
                if self.instance and self.instance.location_id:
                    loc_pks.append(self.instance.location_id)
                self.fields['location'].queryset = Location.objects.filter(
                    pk__in=loc_pks
                ).order_by('name')
            else:
                self.fields['location'].queryset = Location.objects.none()
        else:
            self.fields['location'].queryset = Location.objects.none()
        if location_readonly:
            self.fields['location'].disabled = True
        if student_readonly:
            self.fields['student'].disabled = True
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        student = cleaned_data.get('student')
        if start and end:
            if end <= start:
                raise forms.ValidationError("Das Enddatum muss nach dem Startdatum liegen.")
            if self._block:
                if start < self._block.start_date or end > self._block.end_date:
                    raise forms.ValidationError(
                        f'Die Daten müssen innerhalb des Blocks liegen '
                        f'({self._block.start_date.strftime("%d.%m.%Y")} – {self._block.end_date.strftime("%d.%m.%Y")}).'
                    )
            if student:
                qs = InternshipAssignment.objects.filter(
                    student=student,
                    start_date__lte=end,
                    end_date__gte=start,
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    conflict = qs.first()
                    raise forms.ValidationError(
                        f'Für diese Nachwuchskraft existiert bereits ein überschneidender Einsatz '
                        f'in „{conflict.schedule_block.name}" '
                        f'({conflict.start_date.strftime("%d.%m.%Y")} – {conflict.end_date.strftime("%d.%m.%Y")}).'
                    )
        unit = cleaned_data.get('unit')
        if unit and unit.pk in self._full_unit_pks:
            raise forms.ValidationError(
                f'Die Organisationseinheit „{unit}" hat ihre maximale Kapazität erreicht.'
            )
        instructor = cleaned_data.get('instructor')
        if instructor and start and end:
            qs = InternshipAssignment.objects.filter(
                instructor=instructor,
                start_date__lte=end,
                end_date__gte=start,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.count() >= 5:
                raise forms.ValidationError(
                    f'„{instructor}" betreut in diesem Zeitraum bereits 5 Nachwuchskräfte (Maximum erreicht).'
                )
        return cleaned_data

    class Meta:
        model = InternshipAssignment
        fields = ['student', 'unit', 'location', 'start_date', 'end_date', 'instructor', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class SeminarLectureForm(forms.ModelForm):
    lecture_date = forms.DateField(
        label='Datum',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    start_time = forms.TimeField(
        label='Beginn',
        widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
    )
    end_time = forms.TimeField(
        label='Ende',
        widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
    )

    field_order = ['topic', 'description', 'speaker_name', 'speaker_email',
                   'location', 'lecture_date', 'start_time', 'end_time']

    class Meta:
        model = SeminarLecture
        fields = ['topic', 'description', 'speaker_name', 'speaker_email', 'location']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        from django.utils import timezone
        self._block = kwargs.pop('block', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            local_start = timezone.localtime(self.instance.start_datetime)
            local_end = timezone.localtime(self.instance.end_datetime)
            self.fields['lecture_date'].initial = local_start.date()
            self.fields['start_time'].initial = local_start.time().replace(microsecond=0)
            self.fields['end_time'].initial = local_end.time().replace(microsecond=0)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'kern-form-check__checkbox')
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    def clean(self):
        from datetime import datetime
        from django.utils import timezone
        cleaned = super().clean()
        date = cleaned.get('lecture_date')
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')
        if not (date and start_time and end_time):
            return cleaned

        if date.weekday() >= 5:
            raise forms.ValidationError('Vorträge können nur Montag bis Freitag stattfinden.')

        if end_time <= start_time:
            raise forms.ValidationError('Die Endzeit muss nach der Startzeit liegen.')

        if self._block:
            if date < self._block.start_date or date > self._block.end_date:
                raise forms.ValidationError(
                    f'Das Datum muss innerhalb des Seminarblocks liegen '
                    f'({self._block.start_date.strftime("%d.%m.%Y")} – '
                    f'{self._block.end_date.strftime("%d.%m.%Y")}).'
                )

        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(date, start_time), tz)
        end_dt = timezone.make_aware(datetime.combine(date, end_time), tz)
        cleaned['start_datetime'] = start_dt
        cleaned['end_datetime'] = end_dt

        if self._block:
            qs = SeminarLecture.objects.filter(
                schedule_block=self._block,
                start_datetime__lt=end_dt,
                end_datetime__gt=start_dt,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            conflict = qs.first()
            if conflict:
                raise forms.ValidationError(
                    f'Zeitlicher Konflikt mit „{conflict.topic}" '
                    f'({conflict.start_datetime:%d.%m.%Y %H:%M} – {conflict.end_datetime:%H:%M}).'
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.start_datetime = self.cleaned_data['start_datetime']
        instance.end_datetime = self.cleaned_data['end_datetime']
        if self._block:
            instance.schedule_block = self._block
        if commit:
            instance.save()
        return instance
