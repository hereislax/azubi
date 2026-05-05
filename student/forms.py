"""
Formulare für die Nachwuchskräfte-Verwaltung.

Enthält ModelForms für Stammdaten, Adressen, Noten und den CSV/XLSX-Import.
"""
# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import forms
from django.forms import inlineformset_factory
from services.models import Adress
from .models import Student, Grade, StudentDocumentTemplate, StudentDocumentTemplateField


StudentDocumentTemplateFieldFormSet = inlineformset_factory(
    StudentDocumentTemplate,
    StudentDocumentTemplateField,
    fields=['key', 'label', 'field_type', 'required', 'help_text', 'options', 'order'],
    extra=1,
    can_delete=True,
    widgets={
        'key':        forms.TextInput(attrs={'class': 'kern-form-input__input', 'placeholder': 'z.B. titel_arbeit'}),
        'label':      forms.TextInput(attrs={'class': 'kern-form-input__input', 'placeholder': 'z.B. Titel der Arbeit'}),
        'field_type': forms.Select(attrs={'class': 'kern-form-input__input'}),
        'required':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        'help_text':  forms.TextInput(attrs={'class': 'kern-form-input__input'}),
        'options':    forms.Textarea(attrs={'class': 'kern-form-input__input', 'rows': 3,
                                            'placeholder': 'Nur bei „Auswahl-Liste" – eine Option pro Zeile'}),
        'order':      forms.NumberInput(attrs={'class': 'kern-form-input__input', 'style': 'max-width:6rem;'}),
    },
)


class StudentForm(forms.ModelForm):
    phone_number = forms.CharField(
        required=False,
        max_length=14,
        label='Telefonnummer',
        widget=forms.TextInput(attrs={
            'data-phone-mask': 'true',
            'placeholder': 'xxxx xxxx xxxx',
            'maxlength': '14',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Gespeicherte Telefonnummer (ohne Leerzeichen) formatiert anzeigen
        if self.instance.pk and self.instance.phone_number:
            digits = self.instance.phone_number.replace(' ', '')
            self.initial['phone_number'] = ' '.join(
                digits[i:i+4] for i in range(0, len(digits), 4)
            )
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    def clean_phone_number(self):
        return self.cleaned_data.get('phone_number', '').replace(' ', '')

    class Meta:
        model = Student
        fields = [
            'gender', 'first_name', 'last_name',
            'date_of_birth', 'place_of_birth', 'phone_number',
            'email_private', 'email_id', 'course', 'employment',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'phone_number': forms.TextInput(attrs={'data-phone-mask': 'true', 'placeholder': 'xxxx xxxx xxxx', 'maxlength': '14'}),
        }


class AdressForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'kern-form-input__input')
            field.required = False  # Adresse ist optional

    class Meta:
        model = Adress
        fields = ['street', 'house_number', 'zip_code', 'city']


class StudentImportForm(forms.Form):
    _ALLOWED_IMPORT_EXTENSIONS = {'csv', 'xlsx'}
    _MAX_IMPORT_SIZE = 10 * 1024 * 1024  # 10 MB

    file = forms.FileField(
        label="Datei (CSV oder .xlsx)",
        help_text="Bitte zuerst die Vorlage herunterladen, ausfüllen und hier hochladen. "
                  "Unterstützt: Excel (.xlsx) oder CSV (Semikolon-getrennt, UTF-8). "
                  "Pflichtfelder: Vorname, Nachname, Geburtsdatum (TT.MM.JJJJ), Geburtsort, "
                  "Geschlecht, Kurs, Beschaeftigungsverhaeltnis. "
                  "Optional: Email_privat, Email_Kennung, Telefon, Status, "
                  "Strasse + Hausnummer + PLZ + Ort (Adresse – nur komplett oder gar nicht).",
        widget=forms.ClearableFileInput(attrs={'class': 'kern-form-input__input', 'accept': '.csv,.xlsx'}),
    )

    def clean_file(self):
        f = self.cleaned_data.get('file')
        if f:
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if ext not in self._ALLOWED_IMPORT_EXTENSIONS:
                raise forms.ValidationError(
                    f'Ungültiges Dateiformat „.{ext}". Erlaubt sind: CSV, XLSX.'
                )
            if f.size > self._MAX_IMPORT_SIZE:
                raise forms.ValidationError('Die Datei ist zu groß (maximal 10 MB).')
        return f


class GradeForm(forms.ModelForm):
    _ALLOWED_ATTACHMENT_EXTENSIONS = {'pdf', 'docx', 'doc', 'jpg', 'jpeg', 'png', 'xlsx', 'csv'}
    _MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB

    attachment = forms.FileField(required=False, label="Anhang (wird in Paperless gespeichert)")

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        if student and student.course and student.course.job_profile_id:
            from course.models import GradeType
            self.fields['grade_type'].queryset = GradeType.objects.filter(
                job_profile=student.course.job_profile
            )
        else:
            from course.models import GradeType
            self.fields['grade_type'].queryset = GradeType.objects.none()
        for name, field in self.fields.items():
            if name == 'attachment':
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'kern-form-input__input')
            else:
                field.widget.attrs.setdefault('class', 'kern-form-input__input')

    def clean_attachment(self):
        f = self.cleaned_data.get('attachment')
        if f:
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if ext not in self._ALLOWED_ATTACHMENT_EXTENSIONS:
                raise forms.ValidationError(
                    f'Ungültiges Dateiformat „.{ext}". '
                    f'Erlaubt sind: PDF, DOCX, DOC, JPG, PNG, XLSX, CSV.'
                )
            if f.size > self._MAX_ATTACHMENT_SIZE:
                raise forms.ValidationError('Die Datei ist zu groß (maximal 20 MB).')
        return f

    class Meta:
        model = Grade
        fields = ['grade_type', 'value', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
