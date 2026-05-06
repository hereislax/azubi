# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für die Services-App: Dokumentenverwaltung, Konten, Einstellungen und Systemkonfiguration."""
import requests
from django.conf import settings
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from services.paperless import PaperlessService
from services.roles import training_director_required
from student.models import Student

# Django-Gruppennamen bleiben deutsch (DB-Werte)
ALL_ROLE_GROUPS = [
    'ausbildungsleitung',
    'ausbildungsreferat',
    'ausbildungskoordination',
    'hausverwaltung',
    'reisekostenstelle',
    'ausbildungsverantwortliche',
]

# Anzeige-Labels für die Benutzeroberfläche (deutsch)
ROLE_LABELS = {
    'ausbildungsleitung': 'Ausbildungsleitung',
    'ausbildungsreferat': 'Ausbildungsreferat',
    'ausbildungskoordination': 'Ausbildungskoordination',
    'hausverwaltung': 'Hausverwaltung',
    'reisekostenstelle': 'Reisekostenstelle',
    'ausbildungsverantwortliche': 'Ausbildungsverantwortliche',
    'koordination_ausbildungsverantwortliche': 'Koordination + Ausbildungsverantwortliche',
    '': 'Keine Rolle',
}

# Bootstrap-Farben je Rolle
ROLE_COLORS = {
    'ausbildungsleitung': 'danger',
    'ausbildungsreferat': 'warning',
    'ausbildungskoordination': 'info',
    'hausverwaltung': 'primary',
    'reisekostenstelle': 'secondary',
    'ausbildungsverantwortliche': 'success',
    'koordination_ausbildungsverantwortliche': 'info',
    '': 'light',
}


def _get_primary_role(user):
    """Ermittelt die primaere Rolle eines Benutzers anhand seiner Gruppenzugehoerigkeiten."""
    group_names = {g.name for g in user.groups.all()}
    if 'ausbildungskoordination' in group_names and 'ausbildungsverantwortliche' in group_names:
        return 'koordination_ausbildungsverantwortliche'
    for role in ALL_ROLE_GROUPS:
        if role in group_names:
            return role
    return ''


@xframe_options_sameorigin
@login_required
def paperless_preview_proxy(request, paperless_doc_id: int):
    """
    Lädt die Dokumentvorschau von Paperless-ngx serverseitig
    und leitet sie an den Browser weiter – umgeht CORS-Probleme.
    """
    try:
        response = requests.get(
            f"{PaperlessService._base()}/api/documents/{paperless_doc_id}/download/",
            headers=PaperlessService._headers(),
            timeout=15,
            stream=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "application/pdf")
        django_response = HttpResponse(response.content, content_type=content_type)
        django_response["Content-Disposition"] = "inline"
        return django_response
    except requests.RequestException:
        raise Http404("Vorschau nicht verfügbar.")



@login_required
#@permission_required("student_documents.view_studentdocument", raise_exception=True)
def document_inbox(request):
    """
    Zeigt alle Dokumente aus Paperless-ngx, die noch keinem
    Korrespondenten zugeordnet sind.
    """
    from course.models import Course
    unassigned = PaperlessService.get_unassigned_documents()
    students = Student.objects.order_by("last_name", "first_name")
    courses = Course.objects.order_by("title")

    return render(request, "services/inbox.html", {
        "documents": unassigned,
        "students": students,
        "courses": courses,
        "PAPERLESS_URL": PaperlessService._base(),
    })


@login_required
#@permission_required("student_documents.add_studentdocument", raise_exception=True)
@require_POST
def assign_document(request, paperless_doc_id):
    """
    Weist ein Paperless-Dokument einer Nachwuchskraft oder einem Kurs zu.
    Das POST-Feld 'assignee' enthält den Typ und die ID, z.B. 'student:azubi-xxxx'
    oder 'course:Kursname'.
    """
    from course.models import Course
    assignee = request.POST.get("assignee", "")

    if assignee.startswith("student:"):
        student_pk = assignee[len("student:"):]
        student = get_object_or_404(Student, pk=student_pk)
        success = PaperlessService.assign_student(
            paperless_doc_id=paperless_doc_id,
            student_id=student.id,
        )
        label = str(student)
    elif assignee.startswith("course:"):
        course_pk = assignee[len("course:"):]
        course = get_object_or_404(Course, pk=course_pk)
        success = PaperlessService.assign_course(
            paperless_doc_id=paperless_doc_id,
            course_title=course.title,
        )
        label = course.title
    else:
        messages.error(request, "Ungültige Auswahl. Bitte Nachwuchskraft oder Kurs wählen.")
        return redirect("services:inbox")

    if success:
        messages.success(request, f'Dokument wurde erfolgreich "{label}" zugewiesen.')
    else:
        messages.error(request, "Fehler bei der Zuweisung. Bitte erneut versuchen.")

    return redirect("services:inbox")


@login_required
@require_POST
def document_update(request, paperless_doc_id):
    """Aktualisiert Metadaten (Titel, Datum) eines Paperless-Dokuments."""
    title = request.POST.get('title', '').strip() or None
    created = request.POST.get('created', '').strip() or None
    success = PaperlessService.update_document(paperless_doc_id, title=title, created=created)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': success})
    if success:
        messages.success(request, 'Dokument aktualisiert.')
    else:
        messages.error(request, 'Fehler beim Aktualisieren.')
    from django.urls import reverse
    from services.redirects import safe_next_url
    return redirect(safe_next_url(request, reverse('services:inbox')))


# ── Paperless settings ────────────────────────────────────────────────────────

@training_director_required
def paperless_settings(request):
    from .models import SiteConfiguration
    config = SiteConfiguration.get()

    test_result = None
    if request.method == 'POST':
        config.paperless_url = request.POST.get('paperless_url', '').strip()
        config.paperless_api_key = request.POST.get('paperless_api_key', '').strip()
        config.save(update_fields=['paperless_url', 'paperless_api_key'])
        messages.success(request, 'Paperless-ngx-Einstellungen wurden gespeichert.')

        # Verbindungstest nach dem Speichern
        try:
            resp = requests.get(
                f"{PaperlessService._base()}/api/",
                headers=PaperlessService._headers(),
                timeout=5,
            )
            if resp.status_code == 200:
                test_result = ('success', 'Verbindung zu Paperless-ngx erfolgreich.')
            else:
                test_result = ('warning', f'Paperless-ngx hat mit Status {resp.status_code} geantwortet.')
        except Exception as e:
            test_result = ('danger', f'Verbindung fehlgeschlagen: {e}')

        return render(request, 'services/paperless_settings.html', {
            'config': config,
            'test_result': test_result,
        })

    return render(request, 'services/paperless_settings.html', {'config': config})


# ── SMTP settings ─────────────────────────────────────────────────────────────

@login_required
def smtp_settings(request):
    test_result = None
    if request.method == 'POST':
        recipient = request.POST.get('test_recipient', '').strip()
        if recipient:
            try:
                from .email import send_mail
                send_mail(
                    subject='Azubi-Portal – SMTP-Test',
                    body_text='Dies ist eine Test-E-Mail vom Azubi-Portal.',
                    recipient_list=[recipient],
                )
                test_result = ('success', f'Test-E-Mail erfolgreich an {recipient} gesendet.')
            except Exception as exc:
                test_result = ('danger', f'Fehler beim Senden: {exc}')
        else:
            test_result = ('warning', 'Bitte eine Empfänger-Adresse angeben.')

    smtp_config = {
        'EMAIL_HOST': settings.EMAIL_HOST,
        'EMAIL_PORT': settings.EMAIL_PORT,
        'EMAIL_HOST_USER': settings.EMAIL_HOST_USER,
        'EMAIL_USE_TLS': settings.EMAIL_USE_TLS,
        'EMAIL_USE_SSL': settings.EMAIL_USE_SSL,
        'DEFAULT_FROM_EMAIL': settings.DEFAULT_FROM_EMAIL,
        'configured': bool(settings.EMAIL_HOST),
    }
    return render(request, 'services/smtp_settings.html', {
        'smtp': smtp_config,
        'test_result': test_result,
    })


@login_required
def paperless_search(request, student_pk: str):
    """AJAX: Volltextsuche in den Paperless-Dokumenten eines Studierenden."""
    from django.core.exceptions import PermissionDenied
    from services.permissions import user_can_access_student
    student = get_object_or_404(Student, pk=student_pk)
    if not user_can_access_student(request.user, student):
        raise PermissionDenied

    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    # Sternchen an jeden Begriff für Präfix-Suche (Whoosh-Syntax)
    prefix_query = ' '.join(w + '*' for w in query.split())
    docs = PaperlessService.search_documents_for_student(student.pk, prefix_query)
    results = [
        {
            'id': doc['id'],
            'title': doc.get('title', ''),
            'document_type_name': doc.get('document_type_name') or '–',
            'created': (doc.get('created') or '')[:10],
            'highlights': (doc.get('__search_hit__') or {}).get('highlights', ''),
        }
        for doc in docs
    ]
    return JsonResponse({'results': results})


@login_required
def paperless_search_course(request, course_pk: str):
    """AJAX: Volltextsuche in den Paperless-Dokumenten eines Kurses."""
    from course.models import Course
    from services.roles import is_training_director, is_training_office
    from django.core.exceptions import PermissionDenied
    # Nur Ausbildungsleitung und Ausbildungsreferat duerfen Kurs-Dokumente durchsuchen
    if not (is_training_director(request.user) or is_training_office(request.user)):
        raise PermissionDenied
    course = get_object_or_404(Course, pk=course_pk)
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    prefix_query = ' '.join(w + '*' for w in query.split())
    docs = PaperlessService.search_documents_for_course(course.title, prefix_query)
    results = [
        {
            'id': doc['id'],
            'title': doc.get('title', ''),
            'document_type_name': doc.get('document_type_name') or '–',
            'created': (doc.get('created') or '')[:10],
            'highlights': (doc.get('__search_hit__') or {}).get('highlights', ''),
        }
        for doc in docs
    ]
    return JsonResponse({'results': results})


# ── Account management ────────────────────────────────────────────────────────

@training_director_required
def account_management(request):
    """Kontoverwaltung: Übersicht aller Benutzer mit Rollen und Zuweisungen."""
    import json
    from django.contrib.auth.models import User
    from dormitory.models import Dormitory, DormitoryManagementProfile
    from student.models import TrainingResponsibleAccess
    from services.models import AusbildungsreferatProfile
    from course.models import JobProfile

    users = User.objects.prefetch_related('groups').order_by('last_name', 'first_name', 'username')

    # Hausverwaltungs-Profile nach Benutzer-ID indizieren
    hv_profiles = {
        hp.user_id: hp
        for hp in DormitoryManagementProfile.objects.select_related('dormitory').all()
    }
    # Ausbildungsverantwortliche: zugewiesene Nachwuchskräfte pro Benutzer
    ps_by_user = {}
    for pa in TrainingResponsibleAccess.objects.values('user_id', 'student_id'):
        ps_by_user.setdefault(pa['user_id'], []).append(pa['student_id'])

    # Ausbildungsreferat-Profile mit Berufsbildern
    training_office_profiles = {
        rp.user_id: rp
        for rp in AusbildungsreferatProfile.objects.prefetch_related('job_profiles').all()
    }

    users_data = []
    for user in users:
        role = _get_primary_role(user)
        hv = hv_profiles.get(user.pk)
        ps_pks = ps_by_user.get(user.pk, [])
        rp = training_office_profiles.get(user.pk)
        users_data.append({
            'user': user,
            'role': role,
            'role_label': ROLE_LABELS.get(role, 'Keine Rolle'),
            'role_color': ROLE_COLORS.get(role, 'light'),
            'hv_dormitory': hv.dormitory if hv else None,
            'hv_dormitory_pk': hv.dormitory_id if hv else '',
            'ps_student_count': len(ps_pks),
            'ps_student_pks_json': json.dumps([str(pk) for pk in ps_pks]),
            'referat_profile': rp,
            'referat_jp_pks_json': json.dumps([str(jp.pk) for jp in rp.job_profiles.all()]) if rp else '[]',
        })

    dormitories = Dormitory.objects.order_by('name')
    students = Student.objects.select_related('course').order_by('last_name', 'first_name')
    job_profiles = JobProfile.objects.order_by('description')

    # Rollen-Statistik für Übersicht
    from collections import Counter
    role_counts = Counter(d['role'] for d in users_data)
    role_stats = [
        {'role': role, 'label': ROLE_LABELS.get(role, role), 'color': ROLE_COLORS.get(role, 'secondary'), 'count': role_counts.get(role, 0)}
        for role in ALL_ROLE_GROUPS
        if role_counts.get(role, 0) > 0
    ]

    return render(request, 'services/account_management.html', {
        'users_data': users_data,
        'dormitories': dormitories,
        'students': students,
        'job_profiles': job_profiles,
        'role_stats': role_stats,
        'all_roles': [
            ('', 'Keine Rolle'),
            ('ausbildungsleitung', 'Ausbildungsleitung'),
            ('ausbildungsreferat', 'Ausbildungsreferat'),
            ('ausbildungskoordination', 'Ausbildungskoordination'),
            ('koordination_ausbildungsverantwortliche', 'Koordination + Ausbildungsverantwortliche'),
            ('hausverwaltung', 'Hausverwaltung'),
            ('reisekostenstelle', 'Reisekostenstelle'),
            ('ausbildungsverantwortliche', 'Ausbildungsverantwortliche'),
        ],
        'role_colors': ROLE_COLORS,
    })


@training_director_required
@require_POST
def account_edit(request, user_pk):
    """Bearbeitet die Rolle und rollenspezifischen Zuweisungen eines Benutzerkontos."""
    import json
    from django.contrib.auth.models import User, Group
    from dormitory.models import Dormitory, DormitoryManagementProfile
    from student.models import TrainingResponsibleAccess

    user = get_object_or_404(User, pk=user_pk)

    # 1. Rolle aktualisieren: alle Rollengruppen entfernen, dann neue zuweisen
    new_role = request.POST.get('rolle', '')
    for group_name in ALL_ROLE_GROUPS:
        try:
            user.groups.remove(Group.objects.get(name=group_name))
        except Group.DoesNotExist:
            pass
    if new_role == 'koordination_ausbildungsverantwortliche':
        for group_name in ('ausbildungskoordination', 'ausbildungsverantwortliche'):
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)
    elif new_role:
        group, _ = Group.objects.get_or_create(name=new_role)
        user.groups.add(group)

    # 2. Hausverwaltung: Wohnheimzuweisung aktualisieren
    DormitoryManagementProfile.objects.filter(user=user).delete()
    if new_role == 'hausverwaltung':
        dormitory_pk = request.POST.get('wohnheim')
        if dormitory_pk:
            try:
                dormitory = Dormitory.objects.get(pk=dormitory_pk)
                DormitoryManagementProfile.objects.create(user=user, dormitory=dormitory)
            except Dormitory.DoesNotExist:
                pass

    # 3. Ausbildungsverantwortliche: Nachwuchskraft-Zuweisungen aktualisieren
    TrainingResponsibleAccess.objects.filter(user=user).delete()
    if new_role in ('ausbildungsverantwortliche', 'koordination_ausbildungsverantwortliche'):
        for student_pk in request.POST.getlist('nachwuchskraefte'):
            try:
                student = Student.objects.get(pk=student_pk)
                TrainingResponsibleAccess.objects.create(
                    user=user, student=student, granted_by=request.user
                )
            except Student.DoesNotExist:
                pass

    # 4. Ausbildungsreferat: Profil mit Berufsbildern und Einzelberechtigungen
    from services.models import AusbildungsreferatProfile
    from course.models import JobProfile
    if new_role == 'ausbildungsreferat':
        profile, _ = AusbildungsreferatProfile.objects.get_or_create(user=user)
        profile.can_manage_dormitory      = 'can_manage_dormitory'      in request.POST
        profile.can_manage_inventory      = 'can_manage_inventory'      in request.POST
        profile.can_manage_absences       = 'can_manage_absences'       in request.POST
        profile.can_approve_vacation      = 'can_approve_vacation'      in request.POST
        profile.can_approve_study_days    = 'can_approve_study_days'    in request.POST
        profile.can_manage_announcements  = 'can_manage_announcements'  in request.POST
        profile.can_manage_interventions  = 'can_manage_interventions'  in request.POST
        profile.save()
        jp_pks = request.POST.getlist('referat_job_profiles')
        profile.job_profiles.set(JobProfile.objects.filter(pk__in=jp_pks))
    else:
        AusbildungsreferatProfile.objects.filter(user=user).delete()

    messages.success(
        request,
        f'Konto "{user.get_full_name() or user.username}" wurde aktualisiert.'
    )
    return redirect('services:account_management')


@login_required
@require_POST
def toggle_training_office_scope(request):
    """Schaltet zwischen 'Meine Berufsbilder' und 'Alle Nachwuchskräfte' um."""
    from services.roles import is_training_office
    if is_training_office(request.user):
        request.session['training_office_show_all'] = not request.session.get('training_office_show_all', False)
    from services.redirects import safe_next_url
    return redirect(safe_next_url(request, '/'))


@training_director_required
@require_POST
def account_toggle_active(request, user_pk):
    """Sperrt oder entsperrt ein Benutzerkonto (nur Ausbildungsleitung)."""
    from django.contrib.auth.models import User
    user = get_object_or_404(User, pk=user_pk)
    if user == request.user:
        messages.error(request, 'Sie können Ihr eigenes Konto nicht sperren.')
    elif user.is_superuser:
        messages.error(request, 'Superuser-Konten können hier nicht gesperrt werden.')
    else:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        action = 'entsperrt' if user.is_active else 'gesperrt'
        messages.success(
            request,
            f'Konto "{user.get_full_name() or user.username}" wurde {action}.'
        )
    return redirect('services:account_management')


# ── Settings ──────────────────────────────────────────────────────────────────

@training_director_required
def settings_overview(request):
    return render(request, 'services/settings_overview.html')


@training_director_required
def settings_content(request):
    from .models import SiteConfiguration
    config = SiteConfiguration.get()
    if request.method == 'POST':
        config.impressum_text = request.POST.get('impressum_text', '')
        config.datenschutz_text = request.POST.get('datenschutz_text', '')
        config.save(update_fields=['impressum_text', 'datenschutz_text'])
        messages.success(request, 'Seiteninhalte wurden gespeichert.')
        return redirect('services:settings_content')
    return render(request, 'services/settings_content.html', {'config': config})


def _get_template_registry():
    """Gibt ein Dict aller verwaltbaren Vorlagen-Typen zurück."""
    from dormitory.models import ReservationTemplate, Dormitory
    from course.models import BlockLetterTemplate, InternshipPlanTemplate, StationLetterTemplate
    from proofoftraining.models import TrainingRecordExportTemplate
    from student.models import StudentDocumentTemplate
    from absence.models import VacationConfirmationTemplate
    from inventory.models import ReceiptTemplate
    return {
        'reservation': {
            'model': ReservationTemplate,
            'label': 'Reservierungsschreiben',
            'icon': 'bi-house-door',
            'has_dormitory': True,
        },
        'block_letter': {
            'model': BlockLetterTemplate,
            'label': 'Zuweisungsschreiben',
            'icon': 'bi-envelope',
            'has_dormitory': False,
            'has_job_profile': True,
        },
        'station_letter': {
            'model': StationLetterTemplate,
            'label': 'Stationsschreiben',
            'icon': 'bi-building',
            'has_dormitory': False,
            'has_job_profile': True,
        },
        'internship_plan': {
            'model': InternshipPlanTemplate,
            'label': 'Praktikumsplan',
            'icon': 'bi-map',
            'has_dormitory': False,
            'has_job_profile': True,
        },
        'export': {
            'model': TrainingRecordExportTemplate,
            'label': 'Exportvorlage (Ausbildungsnachweis)',
            'icon': 'bi-journal-text',
            'has_dormitory': False,
        },
        'student_doc': {
            'model': StudentDocumentTemplate,
            'label': 'Dokumentvorlage (Nachwuchskraft)',
            'icon': 'bi-person-vcard',
            'has_dormitory': False,
        },
        'vacation_confirmation': {
            'model': VacationConfirmationTemplate,
            'label': 'Urlaubsbestätigung',
            'icon': 'bi-calendar-check',
            'has_dormitory': False,
        },
        'receipt': {
            'model': ReceiptTemplate,
            'label': 'Ausgabequittung (Inventar)',
            'icon': 'bi-receipt',
            'has_dormitory': False,
        },
    }


@training_director_required
def settings_templates(request):
    from dormitory.models import Dormitory
    registry = _get_template_registry()
    active_tab = request.GET.get('tab', 'reservation')
    if active_tab not in registry:
        active_tab = 'reservation'

    if request.method == 'POST':
        tab = request.POST.get('tab', 'reservation')
        if tab not in registry:
            tab = 'reservation'
        template_type_info = registry[tab]
        Model = template_type_info['model']
        action = request.POST.get('action')

        if action == 'delete':
            pk = request.POST.get('pk')
            try:
                template_obj = Model.objects.get(pk=pk)
                name = template_obj.name
                template_obj.template_file.delete(save=False)
                template_obj.delete()
                messages.success(request, f'Vorlage "{name}" wurde gelöscht.')
            except Model.DoesNotExist:
                messages.error(request, 'Vorlage nicht gefunden.')
        elif action == 'toggle':
            pk = request.POST.get('pk')
            try:
                template_obj = Model.objects.get(pk=pk)
                template_obj.is_active = not template_obj.is_active
                template_obj.save(update_fields=['is_active'])
            except Model.DoesNotExist:
                pass
        elif action == 'upload':
            name = request.POST.get('name', '').strip()
            is_active = 'is_active' in request.POST
            file = request.FILES.get('template_file')
            if not name or not file:
                messages.error(request, 'Bitte Name und Datei angeben.')
            else:
                from services.validators import validate_docx
                from django.core.exceptions import ValidationError
                try:
                    validate_docx(file)
                except ValidationError as e:
                    messages.error(request, str(e.message))
                    return redirect(f"{request.path}?tab={tab}")
                kwargs = {'name': name, 'template_file': file, 'is_active': is_active}
                if template_type_info['has_dormitory']:
                    dormitory_pk = request.POST.get('dormitory') or None
                    dormitory = None
                    if dormitory_pk:
                        try:
                            dormitory = Dormitory.objects.get(pk=dormitory_pk)
                        except Dormitory.DoesNotExist:
                            pass
                    kwargs['dormitory'] = dormitory
                if template_type_info.get('has_job_profile'):
                    from course.models import JobProfile
                    job_profile_pk = request.POST.get('job_profile') or None
                    job_profile = None
                    if job_profile_pk:
                        try:
                            job_profile = JobProfile.objects.get(pk=job_profile_pk)
                        except JobProfile.DoesNotExist:
                            pass
                    kwargs['job_profile'] = job_profile
                Model.objects.create(**kwargs)
                messages.success(request, f'Vorlage "{name}" wurde hochgeladen.')

        return redirect(f"{request.path}?tab={tab}")

    placeholder_help = _build_placeholder_help()
    # Tabs mit Vorlagen aufbauen
    tabs = []
    for key, template_type_info in registry.items():
        qs = template_type_info['model'].objects.all()
        if template_type_info['has_dormitory']:
            qs = qs.select_related('dormitory')
        if template_type_info.get('has_job_profile'):
            qs = qs.select_related('job_profile')
        tabs.append({
            'key': key,
            'label': template_type_info['label'],
            'icon': template_type_info['icon'],
            'has_dormitory': template_type_info['has_dormitory'],
            'has_job_profile': template_type_info.get('has_job_profile', False),
            'templates': qs.order_by('-uploaded_at'),
            'active': key == active_tab,
            'placeholder_help': placeholder_help.get(key, ''),
        })

    from course.models import JobProfile
    return render(request, 'services/settings_templates.html', {
        'tabs': tabs,
        'active_tab': active_tab,
        'dormitories': Dormitory.objects.order_by('name'),
        'job_profiles': JobProfile.objects.order_by('description'),
    })


def _build_placeholder_help():
    """Baut die Hilfetexte für die Vorlagen-Editor-Seite aus document.conventions.

    Die Tag-Liste pro Vorlagentyp wird zentral in :mod:`document.conventions`
    gepflegt – diese Funktion stellt für jeden Tab einen vorformatierten
    Hilfetext bereit. So bleiben Code und Editor-Hinweise synchron.
    """
    from document.conventions import (
        STUDENT_TAGS, COURSE_TAGS, BLOCK_TAGS, EINSATZ_TAGS, INSTRUCTOR_TAGS,
        DORMITORY_TAGS, INVENTORY_TAGS, CREATOR_TAGS, META_TAGS,
        format_help_block,
    )

    student_block = format_help_block(STUDENT_TAGS, COURSE_TAGS, CREATOR_TAGS, META_TAGS)
    return {
        'reservation':           format_help_block(STUDENT_TAGS, DORMITORY_TAGS, CREATOR_TAGS, META_TAGS),
        'block_letter':          format_help_block(STUDENT_TAGS, COURSE_TAGS, BLOCK_TAGS, CREATOR_TAGS, META_TAGS,
                                                   list_hints=['{{ freitext }}']),
        'station_letter':        format_help_block(STUDENT_TAGS, COURSE_TAGS, BLOCK_TAGS, EINSATZ_TAGS, CREATOR_TAGS, META_TAGS,
                                                   list_hints=['{{ freitext }}, {{ anrede }}']),
        'internship_plan':       format_help_block(STUDENT_TAGS, COURSE_TAGS, BLOCK_TAGS, CREATOR_TAGS, META_TAGS,
                                                   list_hints=['{{ freitext }}, {{ anrede }}',
                                                               'Liste {% for e in einsaetze %}: {{ e.einheit }}, {{ e.beginn }}, {{ e.ende }}, {{ e.standort }}, {{ e.praxistutor }}']),
        'export':                format_help_block(STUDENT_TAGS, COURSE_TAGS, CREATOR_TAGS, META_TAGS,
                                                   list_hints=['Liste {% for n in nachweise %}: {{ n.kw }}, {{ n.jahr }}, {{ n.von }}, {{ n.bis }}, {{ n.status }}',
                                                               'Tage {% for t in n.tage %}: {{ t.datum }}, {{ t.wochentag }}, {{ t.art }}, {{ t.beschreibung }}']),
        'student_doc':           student_block,
        'vacation_confirmation': format_help_block(CREATOR_TAGS, META_TAGS,
                                                   list_hints=['{{ bearbeitet_von }}',
                                                               'Liste {% for a in antraege %}: {{ a.vorname }}, {{ a.nachname }}, {{ a.kurs }}, {{ a.von }}, {{ a.bis }}, {{ a.arbeitstage }}, {{ a.antragsart }}']),
        'receipt':               format_help_block(STUDENT_TAGS, INVENTORY_TAGS, CREATOR_TAGS, META_TAGS),
    }


_COLOR_FIELDS = {
    'brand_primary_color':   '#0d6efd',
    'brand_secondary_color': '#6c757d',
    'brand_success_color':   '#198754',
    'brand_danger_color':    '#dc3545',
    'brand_warning_color':   '#ffc107',
    'brand_info_color':      '#0dcaf0',
}


from services.colors import BUNDESFARBEN as _BUNDESFARBEN  # noqa: E402


@training_director_required
def settings_appearance(request):
    from .models import SiteConfiguration
    config = SiteConfiguration.get()
    if request.method == 'POST':
        name = request.POST.get('brand_name', '').strip() or 'azubi.'
        config.brand_name = name
        config.brand_header = request.POST.get('brand_header', '').strip()
        fields = ['brand_name', 'brand_header']
        for field, default in _COLOR_FIELDS.items():
            hex_value = request.POST.get(field, default).strip()
            if not (hex_value.startswith('#') and len(hex_value) == 7):
                hex_value = default
            setattr(config, field, hex_value)
            fields.append(field)
        config.save(update_fields=fields)
        messages.success(request, 'Erscheinungsbild wurde gespeichert.')
        return redirect('services:settings_appearance')
    return render(request, 'services/settings_appearance.html', {
        'config': config,
        'bundesfarben': _BUNDESFARBEN,
    })


@training_director_required
def settings_tasks(request):
    from .models import SiteConfiguration
    config = SiteConfiguration.get()

    errors = {}
    if request.method == 'POST':
        def _int(key, default, lo=0, hi=999):
            try:
                v = int(request.POST.get(key, default))
                if not (lo <= v <= hi):
                    raise ValueError
                return v
            except (ValueError, TypeError):
                errors[key] = True
                return default

        fields = {
            'reminder_days_before_start':       _int('reminder_days_before_start', config.reminder_days_before_start, 1, 90),
            'reminder_days_before_end':         _int('reminder_days_before_end',   config.reminder_days_before_end,   1, 90),
            'reminder_hour':                    _int('reminder_hour',   config.reminder_hour,   0, 23),
            'reminder_minute':                  _int('reminder_minute', config.reminder_minute, 0, 59),
            'escalation_stage1_days':           _int('escalation_stage1_days', config.escalation_stage1_days, 1, 90),
            'escalation_stage2_days':           _int('escalation_stage2_days', config.escalation_stage2_days, 1, 90),
            'escalation_final_days':            _int('escalation_final_days',  config.escalation_final_days,  1, 90),
            'assessment_escalation_hour':       _int('assessment_escalation_hour',   config.assessment_escalation_hour,   0, 23),
            'assessment_escalation_minute':     _int('assessment_escalation_minute', config.assessment_escalation_minute, 0, 59),
            'vacation_batch_hour':              _int('vacation_batch_hour',   config.vacation_batch_hour,   0, 23),
            'vacation_batch_minute':            _int('vacation_batch_minute', config.vacation_batch_minute, 0, 59),
            'sick_leave_report_hour':           _int('sick_leave_report_hour',   config.sick_leave_report_hour,   0, 23),
            'sick_leave_report_minute':         _int('sick_leave_report_minute', config.sick_leave_report_minute, 0, 59),
            'anonymization_months':             _int('anonymization_months', config.anonymization_months, 1, 120),
            'anonymization_hour':               _int('anonymization_hour',   config.anonymization_hour,   0, 23),
            'anonymization_minute':             _int('anonymization_minute', config.anonymization_minute, 0, 59),
            'paperless_cache_interval_seconds': _int('paperless_cache_interval_seconds', config.paperless_cache_interval_seconds, 30, 3600),
        }
        if not errors:
            for field, value in fields.items():
                setattr(config, field, value)
            config.save(update_fields=list(fields.keys()))
            messages.success(request, 'Einstellungen gespeichert.')
            return redirect('services:settings_tasks')
        else:
            messages.error(request, 'Bitte alle Felder korrekt ausfüllen.')

    return render(request, 'services/settings_tasks.html', {'config': config, 'errors': errors})


def theme_css(request):
    """Dynamisches CSS mit den Markenfarben aus SiteConfiguration."""
    from .models import SiteConfiguration
    config = SiteConfiguration.get()

    def hex_to_rgb(h):
        h = (h or '#000000').lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def darken(h, f=0.85):
        r, g, b = hex_to_rgb(h)
        return '#{:02x}{:02x}{:02x}'.format(int(r*f), int(g*f), int(b*f))

    def text_color(h):
        r, g, b = hex_to_rgb(h)
        return '#ffffff' if (0.299*r + 0.587*g + 0.114*b) / 255 < 0.55 else '#212529'

    def color_block(name, hex_color):
        r, g, b = hex_to_rgb(hex_color)
        dark = darken(hex_color)
        darker = darken(hex_color, 0.7)
        text_on_color = text_color(hex_color)
        return f"""
:root {{
    --bs-{name}: {hex_color};
    --bs-{name}-rgb: {r}, {g}, {b};
}}
.bg-{name} {{ background-color: {hex_color} !important; }}
.text-{name} {{ color: {hex_color} !important; }}
.border-{name} {{ border-color: {hex_color} !important; }}
.badge.bg-{name}, .badge.text-bg-{name} {{ background-color: {hex_color} !important; color: {text_on_color} !important; }}
.btn-{name} {{
    --bs-btn-bg: {hex_color}; --bs-btn-border-color: {hex_color}; --bs-btn-color: {text_on_color};
    --bs-btn-hover-bg: {dark}; --bs-btn-hover-border-color: {dark}; --bs-btn-hover-color: {text_on_color};
    --bs-btn-active-bg: {darker}; --bs-btn-active-border-color: {darker}; --bs-btn-active-color: {text_on_color};
    --bs-btn-focus-shadow-rgb: {r}, {g}, {b};
}}
.btn-outline-{name} {{
    --bs-btn-color: {hex_color}; --bs-btn-border-color: {hex_color};
    --bs-btn-hover-bg: {hex_color}; --bs-btn-hover-border-color: {hex_color}; --bs-btn-hover-color: {text_on_color};
    --bs-btn-active-bg: {hex_color}; --bs-btn-active-border-color: {hex_color}; --bs-btn-active-color: {text_on_color};
    --bs-btn-focus-shadow-rgb: {r}, {g}, {b};
}}
.alert-{name} {{ --bs-alert-color: {darker}; --bs-alert-border-color: {hex_color}; }}
"""

    primary   = config.brand_primary_color   or '#0d6efd'
    secondary = config.brand_secondary_color or '#6c757d'
    success   = config.brand_success_color   or '#198754'
    danger    = config.brand_danger_color    or '#dc3545'
    warning   = config.brand_warning_color   or '#ffc107'
    info      = config.brand_info_color      or '#0dcaf0'

    primary_r, primary_g, primary_b = hex_to_rgb(primary)
    primary_dark   = darken(primary)
    primary_darker = darken(primary, 0.7)
    primary_text_color = text_color(primary)

    css = color_block('primary',   primary)
    css += color_block('secondary', secondary)
    css += color_block('success',   success)
    css += color_block('danger',    danger)
    css += color_block('warning',   warning)
    css += color_block('info',      info)

    css += f"""
/* Primary extras */
:root {{
    --bs-link-color: {primary};
    --bs-link-color-rgb: {primary_r}, {primary_g}, {primary_b};
    --bs-link-hover-color: {primary_dark};
    --bs-pagination-active-bg: {primary};
    --bs-pagination-active-border-color: {primary};
    --bs-pagination-color: {primary};
    --bs-pagination-hover-color: {primary_dark};
    --bs-pagination-focus-box-shadow: 0 0 0 0.2rem rgba({primary_r}, {primary_g}, {primary_b}, 0.2);
    --dt-row-selected: {primary_r}, {primary_g}, {primary_b};
}}
a {{ color: {primary}; }}
a:hover {{ color: {primary_dark}; }}
.navbar.bg-primary {{ background-color: {primary} !important; }}
.navbar.bg-primary .navbar-brand,
.navbar.bg-primary .nav-link {{ color: {primary_text_color} !important; }}
.navbar.bg-primary .nav-link:hover {{ background-color: rgba(0,0,0,.1); }}
.nav-pills .nav-link.active {{ background-color: {primary} !important; color: {primary_text_color} !important; }}
.nav-tabs .nav-link.active {{ border-bottom-color: {primary}; color: {primary}; font-weight: 600; }}
.nav-tabs .nav-link:hover {{ color: {primary}; }}
/* ── KERN Form-States – KERN-Spec, theme-primary statt #171A2B ── */

/* Inputs: Hover färbt nur den Bottom-Border. Andere Borders sind transparent
   (KERN-CDN), also reicht die Color-Änderung. */
.kern-form-input__input:hover:not(:focus):not(:disabled) {{
    border-bottom-color: {primary} !important;
}}
/* Focus exakt nach KERN: outline-color = primary, Bootstrap-Glow killen.
   Bootstrap's generic `input:focus` setzt einen blauen Glow-Ring
   matched auf ALLE inputs (Specificity 0,1,1) – wir killen den Schatten und
   überschreiben outline mit Theme-Farbe. */
.kern-form-input__input:focus {{
    outline: 4px solid {primary} !important;
    outline-offset: 0 !important;
    box-shadow: none !important;
    border: none !important;
}}

/* Selects: Wrapper trägt den Bottom-Border */
.kern-form-input__select-wrapper:hover {{
    border-bottom-color: {primary} !important;
}}
/* Select-Fokus: Bootstrap-Glow killen, Theme-Farbe für Outline */
.kern-form-input__select:focus {{
    outline-color: {primary} !important;
    box-shadow: none !important;
    border-color: transparent !important;
}}
.kern-form-input__select-wrapper:has(.kern-form-input__select:focus) {{
    border-bottom-color: {primary} !important;
}}

/* Checkboxen/Radios: Border-Box + konstante 2px Border auf ALLEN States,
   damit der Content-Bereich nicht wandert (KERN-CDN setzt Border auf focus
   auf 0px, was den Inhalt um 4px verschiebt → Häkchen jumpt). */
.kern-form-check__checkbox,
.kern-form-check__radio {{
    box-sizing: border-box !important;
    border-width: 2px !important;
    border-style: solid !important;
}}
.kern-form-check__checkbox:hover,
.kern-form-check__checkbox:focus,
.kern-form-check__checkbox:focus-visible,
.kern-form-check__checkbox:checked,
.kern-form-check__checkbox:checked:hover,
.kern-form-check__checkbox:checked:focus,
.kern-form-check__checkbox:checked:focus-visible,
.kern-form-check__radio:hover,
.kern-form-check__radio:focus,
.kern-form-check__radio:focus-visible,
.kern-form-check__radio:checked,
.kern-form-check__radio:checked:hover,
.kern-form-check__radio:checked:focus,
.kern-form-check__radio:checked:focus-visible {{
    border-width: 2px !important;
    border-style: solid !important;
}}
/* Hover/Focus-Farbe = primary */
.kern-form-check__checkbox:hover:not(:disabled),
.kern-form-check__radio:hover:not(:disabled) {{
    border-color: {primary} !important;
}}
.kern-form-check__checkbox:focus,
.kern-form-check__checkbox:focus-visible,
.kern-form-check__radio:focus,
.kern-form-check__radio:focus-visible {{
    border-color: {primary} !important;
    box-shadow: 0 0 0 3px {primary} !important;
    outline: none !important;
}}
/* Häkchen-:before – KERN-Default-Positioning beibehalten (relative + left:3px,
   top:8px, margin:4px), aber margin auf ALLEN State-Kombinationen 4px fixieren.
   KERN-CDN variiert margin zwischen 2/4/6px je State zur Border-Kompensation,
   was bei uns (konstante 2px-Border) den Haken verschiebt. */
.kern-form-check__checkbox:before,
.kern-form-check__checkbox:hover:before,
.kern-form-check__checkbox:focus:before,
.kern-form-check__checkbox:focus-visible:before,
.kern-form-check__checkbox:checked:before,
.kern-form-check__checkbox:checked:hover:before,
.kern-form-check__checkbox:checked:focus:before,
.kern-form-check__checkbox:checked:focus-visible:before {{
    margin: 4px !important;
}}
/* Häkchen-Border-Farbe = primary */
.kern-form-check__checkbox:checked:before {{
    border-color: {primary} !important;
}}
.kern-form-check__radio:checked:before {{
    background-color: {primary} !important;
}}
.breadcrumb-item.active {{ color: {primary}; }}
.card-header.bg-primary {{ background-color: {primary} !important; color: {primary_text_color} !important; }}
.bg-primary.bg-opacity-10 {{ background-color: rgba({primary_r}, {primary_g}, {primary_b}, 0.08) !important; }}
.text-primary {{ color: {primary} !important; }}
/* Fokus-Indikatoren (Barrierefreiheit) – KERN-Form-Elemente bringen ihre eigenen,
   schließe sie aus, sonst überlagert dieser generische Ring den KERN-State. */
:focus-visible:not(.kern-form-input__input):not(.kern-form-input__select):not(.kern-form-check__checkbox):not(.kern-form-check__radio):not(.kern-btn) {{
    outline: 3px solid rgba({primary_r}, {primary_g}, {primary_b}, 0.5) !important;
    outline-offset: 2px !important;
}}
/* DataTables */
.page-item.active .page-link {{ background-color: {primary} !important; border-color: {primary} !important; color: {primary_text_color} !important; }}
.page-link {{ color: {primary}; }}
.page-link:hover {{ color: {primary_dark}; background-color: rgba({primary_r}, {primary_g}, {primary_b}, 0.06); }}
.page-link:focus {{ box-shadow: 0 0 0 0.2rem rgba({primary_r}, {primary_g}, {primary_b}, 0.2); }}
table.dataTable thead>tr>th span.dt-column-order:before,
table.dataTable thead>tr>th span.dt-column-order:after,
table.dataTable thead>tr>td span.dt-column-order:before,
table.dataTable thead>tr>td span.dt-column-order:after {{ color: {primary}; }}
/* Dropdown aktive Elemente */
.dropdown-item:active {{ background-color: {primary}; color: {primary_text_color}; }}
/* Fortschrittsbalken */
.progress-bar {{ background-color: {primary}; }}

/* ── KERN UX CSS-Variablen-Mapping (dynamische Markenfarben → KERN-Tokens) ──── */
:root {{
    /* Aktionsfarben */
    --kern-color-action-default: {primary};
    --kern-color-action-hover: {primary_dark};
    --kern-color-action-active: {primary_darker};
    --kern-color-action-on-default: {primary_text_color};
    /* Feedback-Farben */
    --kern-color-feedback-danger-default: {danger};
    --kern-color-feedback-success-default: {success};
    --kern-color-feedback-warning-default: {warning};
    --kern-color-feedback-info-default: {info};
    /* Layout-Farben */
    --kern-color-layout-background-default: #f0f2f5;
    --kern-color-layout-text-default: #1b1b1b;
    --kern-color-layout-text-muted: #6c757d;
    --kern-color-layout-border-default: #d8dce3;
    --kern-color-layout-border-focus: {primary};
    /* Fokus-Ring */
    --kern-focus-outline-color: rgba({primary_r}, {primary_g}, {primary_b}, 0.45);
}}
"""
    resp = HttpResponse(css, content_type='text/css; charset=utf-8')
    resp['Cache-Control'] = 'no-cache'
    return resp


def _logo_colors():
    """Gibt (primary, light, dark) für die Logo-SVGs zurück."""
    from .models import SiteConfiguration

    config = SiteConfiguration.get()
    primary = config.brand_primary_color or '#0d6efd'

    def hex_to_rgb(h):
        h = (h or '#000000').lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r, g, b = hex_to_rgb(primary)
    # Lighter variant: mix 40 % toward white
    light = '#{:02x}{:02x}{:02x}'.format(
        int(r + (255 - r) * 0.4),
        int(g + (255 - g) * 0.4),
        int(b + (255 - b) * 0.4),
    )
    # Darker variant
    dark = '#{:02x}{:02x}{:02x}'.format(int(r * 0.75), int(g * 0.75), int(b * 0.75))
    return primary, light, dark


def favicon_svg(request):
    """Favicon als SVG mit dynamischer Primärfarbe."""
    primary, light, dark = _logo_colors()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{light}" />
      <stop offset="100%" style="stop-color:{primary}" />
    </linearGradient>
  </defs>
  <rect x="1" y="11" width="19" height="19" rx="5" fill="{primary}" opacity="0.18"/>
  <rect x="8"  y="3"  width="19" height="19" rx="5" fill="url(#g)"/>
</svg>"""
    resp = HttpResponse(svg, content_type='image/svg+xml; charset=utf-8')
    resp['Cache-Control'] = 'no-cache'
    return resp


def logo_svg(request):
    """Logo-Icon als SVG mit dynamischer Primärfarbe."""
    primary, light, dark = _logo_colors()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100">
  <defs>
    <linearGradient id="bl" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{light}" />
      <stop offset="100%" style="stop-color:{primary}" />
    </linearGradient>
  </defs>

  <!-- Small icon: two overlapping rounded squares (modules/people) -->
  <g transform="translate(16, 24)">
    <rect x="0" y="12" width="28" height="28" rx="7" fill="{primary}" opacity="0.18"/>
    <rect x="10" y="4" width="28" height="28" rx="7" fill="url(#bl)"/>
  </g>

  <!-- Wordmark -->
  <text x="68" y="62" font-family="'DM Sans', 'Manrope', 'Plus Jakarta Sans', sans-serif"
        font-size="48" font-weight="800" letter-spacing="-0.5" fill="#0F172A">
    azubi
  </text>

  <!-- Subtle colored dot after the text -->
  <circle cx="195" cy="58" r="5" fill="url(#bl)"/>
</svg>"""
    resp = HttpResponse(svg, content_type='image/svg+xml; charset=utf-8')
    #resp['Cache-Control'] = 'no-cache'
    return resp


def logo_text_svg(request):
    """Logo mit Tagline als SVG mit dynamischer Primärfarbe."""
    primary, light, dark = _logo_colors()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 100" width="380" height="100">
  <defs>
    <linearGradient id="bl" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{light}" />
      <stop offset="100%" style="stop-color:{primary}" />
    </linearGradient>
  </defs>

  <!-- Small icon: two overlapping rounded squares (modules/people) -->
  <g transform="translate(16, 24)">
    <rect x="0" y="12" width="28" height="28" rx="7" fill="{primary}" opacity="0.18"/>
    <rect x="10" y="4" width="28" height="28" rx="7" fill="url(#bl)"/>
  </g>

  <!-- Wordmark -->
  <text x="68" y="62" font-family="'DM Sans', 'Manrope', 'Plus Jakarta Sans', sans-serif"
        font-size="48" font-weight="800" letter-spacing="-0.5" fill="#0F172A">
    azubi
  </text>

  <!-- Subtle colored dot after the text -->
  <circle cx="195" cy="58" r="5" fill="url(#bl)"/>

  <!-- Tagline -->
  <text x="70" y="82" font-family="'DM Sans', 'Manrope', 'Plus Jakarta Sans', sans-serif"
        font-size="10" fill="#64748B" letter-spacing="3" font-weight="500">
    AUSBILDUNGSMANAGEMENT
  </text>
</svg>"""
    resp = HttpResponse(svg, content_type='image/svg+xml; charset=utf-8')
    #resp['Cache-Control'] = 'no-cache'
    return resp


def manifest_json(request):
    """Dynamisches PWA-Manifest mit Brand-Konfiguration."""
    import json
    from .models import SiteConfiguration

    config = SiteConfiguration.get()
    name = config.brand_name or 'azubi.'
    color = config.brand_primary_color or '#0d6efd'

    manifest = {
        'name': name,
        'short_name': name,
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': color,
        'lang': 'de',
        'icons': [
            {
                'src': settings.STATIC_URL + 'img/icon-192.png',
                'sizes': '192x192',
                'type': 'image/png',
            },
            {
                'src': settings.STATIC_URL + 'img/icon-512.png',
                'sizes': '512x512',
                'type': 'image/png',
            },
        ],
    }
    resp = HttpResponse(
        json.dumps(manifest, ensure_ascii=False),
        content_type='application/manifest+json; charset=utf-8',
    )
    resp['Cache-Control'] = 'no-cache'
    return resp


def sw_js(request):
    """Service Worker vom Root-Pfad ausliefern (maximaler Scope)."""
    import pathlib

    sw_path = pathlib.Path(settings.STATICFILES_DIRS[0]) / 'js' / 'sw.js'
    content = sw_path.read_text(encoding='utf-8')
    resp = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    resp['Cache-Control'] = 'no-cache'
    resp['Service-Worker-Allowed'] = '/'
    return resp


_MODULE_FIELDS = [
    ('module_dormitory',       'Wohnheimverwaltung',    'bi-building',           'Zimmerreservierungen, Belegungsplan und Wohnheimverwaltung.'),
    ('module_inventory',       'Inventar',              'bi-archive',            'Inventarverwaltung und Gerätezuweisungen.'),
    ('module_absence',         'Abwesenheiten',         'bi-calendar-x',         'Urlaubsanträge und Krankmeldungen.'),
    ('module_studyday',        'Lerntage',              'bi-book',               'Lerntags-Anträge und -Genehmigungen.'),
    ('module_assessment',      'Beurteilungen',         'bi-clipboard-check',    'Stationsbeurteilungen und Feedback.'),
    ('module_intervention',    'Maßnahmen',             'bi-shield-exclamation', 'Interventionen und Maßnahmen-Dokumentation.'),
    ('module_announcements',   'Ankündigungen',         'bi-megaphone',          'Ankündigungen für Nachwuchskräfte.'),
    ('module_knowledge',       'Wissensdatenbank',      'bi-journal-bookmark',   'Informationen und Dokumente für Nachwuchskräfte.'),
    ('module_proofoftraining', 'Ausbildungsnachweise',  'bi-journal-text',       'Wöchentliche Ausbildungsnachweise der Nachwuchskräfte.'),
    ('module_auditlog',        'Audit-Log',             'bi-journal-text',       'Protokoll aller Datenänderungen.'),
]


@training_director_required
def settings_modules(request):
    from .models import SiteConfiguration
    config = SiteConfiguration.get()

    if request.method == 'POST':
        update_fields = []
        for field, *_ in _MODULE_FIELDS:
            value = field in request.POST
            setattr(config, field, value)
            update_fields.append(field)
        config.save(update_fields=update_fields)
        messages.success(request, 'Module-Konfiguration gespeichert.')
        return redirect('services:settings_modules')

    modules = [
        {'field': field, 'label': label, 'icon': icon, 'description': desc, 'enabled': getattr(config, field)}
        for field, label, icon, desc in _MODULE_FIELDS
    ]
    return render(request, 'services/settings_modules.html', {'modules': modules})


@training_director_required
def settings_system(request):
    """Zeigt Systeminformationen: Python-, Django-, DB-Version und Paperless-Status."""
    import sys
    import django
    from django.contrib.auth.models import User
    from django.db import connection

    db_version = None
    db_size = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            db_version = cursor.fetchone()[0]
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            db_size = cursor.fetchone()[0]
    except Exception:
        pass

    paperless_ok = False
    paperless_error = None
    try:
        resp = requests.get(
            f"{PaperlessService._base()}/api/",
            headers=PaperlessService._headers(),
            timeout=5,
        )
        paperless_ok = resp.status_code == 200
    except Exception as e:
        paperless_error = str(e)

    return render(request, 'services/settings_system.html', {
        'django_version': django.get_version(),
        'python_version': sys.version.split()[0],
        'db_version': db_version,
        'db_size': db_size,
        'user_count': User.objects.count(),
        'student_count': Student.objects.count(),
        'paperless_ok': paperless_ok,
        'paperless_error': paperless_error,
        'paperless_url': PaperlessService._base(),
    })

# ── Interne Benachrichtigungen ─────────────────────────────────────────────────

@login_required
def notifications_list(request):
    from .models import Notification
    from django.utils import timezone

    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:100]

    if request.method == 'POST' and 'mark_all_read' in request.POST:
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        messages.success(request, 'Alle Benachrichtigungen als gelesen markiert.')
        return redirect('notifications')

    return render(request, 'services/notifications.html', {'notifs': notifs})


@login_required
def notification_preferences(request):
    """Benachrichtigungseinstellungen: Benutzer kann einzelne E-Mail-Typen deaktivieren."""
    from .models import UserNotificationPreference, CONFIGURABLE_NOTIFICATION_KEYS
    from services.roles import (
        is_training_coordinator, is_training_director, is_training_office,
    )

    prefs, _ = UserNotificationPreference.objects.get_or_create(user=request.user)

    # Relevante Schluessel je nach Benutzerrolle ermitteln
    is_student = hasattr(request.user, 'student_profile')
    is_chief = is_training_coordinator(request.user)
    is_staff_role = is_training_director(request.user) or is_training_office(request.user)

    student_keys = {'proof_of_training_reminder', 'proof_of_training_approved', 'proof_of_training_rejected'}
    chief_keys = {'chief_assignment'}
    staff_keys = {'assignment_approved', 'assignment_rejected'}

    visible_keys = set()
    if is_student:
        visible_keys |= student_keys
    if is_chief:
        visible_keys |= chief_keys
    if is_staff_role:
        visible_keys |= staff_keys

    available = [(key, label) for key, label in CONFIGURABLE_NOTIFICATION_KEYS if key in visible_keys]

    if request.method == 'POST':
        # Angehakt = aktiviert; nicht angehakt = deaktiviert
        new_disabled = [
            key for key, _ in available
            if request.POST.get(f'pref_{key}') != '1'
        ]
        prefs.disabled_keys = new_disabled
        prefs.save(update_fields=['disabled_keys'])
        messages.success(request, 'Benachrichtigungseinstellungen gespeichert.')
        return redirect('services:notification_preferences')

    disabled = set(prefs.disabled_keys or [])
    available_with_status = [(key, label, key not in disabled) for key, label in available]

    return render(request, 'services/notification_preferences.html', {
        'available_with_status': available_with_status,
        'has_options': bool(available),
    })


@login_required
def mein_konto(request):
    """Mein Konto: Passwort aendern und Profildaten bearbeiten."""
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash
    from allauth.socialaccount.models import SocialAccount, SocialApp
    from .models import UserProfile

    profile = getattr(request.user, 'profile', None)
    student_profile = getattr(request.user, 'student_profile', None)
    chief_profile = getattr(request.user, 'chief_instructor_profile', None)

    password_form = PasswordChangeForm(request.user)

    # SSO-Verknüpfung des angemeldeten Users (max. 1 wegen OneToOne-Constraint).
    external_identity = SocialAccount.objects.filter(user=request.user).first()
    external_provider_name = ''
    if external_identity is not None:
        app = SocialApp.objects.filter(provider=external_identity.provider).first()
        external_provider_name = app.name if app else external_identity.provider

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'change_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Passwort wurde erfolgreich geändert.')
                return redirect('services:mein_konto')

        elif action == 'save_profile' and profile:
            profile.job_title = request.POST.get('job_title', '').strip()
            profile.room = request.POST.get('room', '').strip()
            profile.phone = request.POST.get('phone', '').strip()
            location_pk = request.POST.get('location') or None
            if location_pk:
                from organisation.models import Location
                try:
                    profile.location = Location.objects.get(pk=location_pk)
                except Location.DoesNotExist:
                    profile.location = None
            else:
                profile.location = None
            profile.save()
            messages.success(request, 'Profildaten wurden gespeichert.')
            return redirect('services:mein_konto')

        elif action == 'unlink_sso' and external_identity is not None:
            # Self-Service-Lösung der SSO-Verknüpfung. post_delete-Signal des
            # auditlog protokolliert die Löschung automatisch (SocialAccount
            # ist im Tracking-Registry hinterlegt).
            provider_name = external_provider_name
            external_identity.delete()
            messages.success(
                request,
                f'Verknüpfung mit {provider_name} wurde gelöst. '
                f'Falls Sie noch kein lokales Passwort gesetzt haben, '
                f'nutzen Sie bitte beim nächsten Login die Funktion '
                f'„Passwort vergessen?".',
            )
            return redirect('services:mein_konto')

    locations = []
    if profile is not None:
        from organisation.models import Location
        locations = Location.objects.order_by('name')

    # 2FA-Status für Profil-Karte: ist mindestens ein TOTP-Gerät bestätigt?
    from django_otp.plugins.otp_totp.models import TOTPDevice as _TOTP
    from django_otp.plugins.otp_static.models import StaticToken as _StaticToken
    mfa_active = _TOTP.objects.filter(user=request.user, confirmed=True).exists()
    mfa_recovery_remaining = _StaticToken.objects.filter(
        device__user=request.user, device__confirmed=True,
    ).count() if mfa_active else 0

    return render(request, 'services/mein_konto.html', {
        'password_form': password_form,
        'profile': profile,
        'student_profile': student_profile,
        'chief_profile': chief_profile,
        'locations': locations,
        'external_identity': external_identity,
        'external_provider_name': external_provider_name,
        'mfa_active': mfa_active,
        'mfa_recovery_remaining': mfa_recovery_remaining,
    })


@login_required
def notification_mark_read(request, pk):
    from .models import Notification
    from django.utils import timezone
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notif.read_at:
        notif.read_at = timezone.now()
        notif.save(update_fields=['read_at'])
    if notif.link:
        return redirect(notif.link)
    return redirect('notifications')


# ── Backup Web-UI (Stufe 4) ──────────────────────────────────────────────────
# Nur Superuser haben Zugriff. Trigger-Buttons werden via POST in Celery
# eingestellt (delay), damit das UI nicht blockiert. Manuelle Restores in die
# Produktiv-DB sind bewusst nur per CLI möglich.

import datetime as _dt
import os
from collections import defaultdict
from pathlib import Path

from django.contrib.auth.decorators import user_passes_test


def _superuser_required(view_func):
    """Erlaubt nur Superusern. Andere bekommen Login-Redirect (statt 403)."""
    return login_required(user_passes_test(lambda u: u.is_superuser)(view_func))


_BACKUP_PREFIXES = {
    'azubi-media-':     ('azubi_media',     'Azubi-Media',    'tar'),
    'azubi-':           ('azubi_db',        'Azubi-DB',       'psql.bin'),
    'paperless-db-':    ('paperless_db',    'Paperless-DB',   'dump'),
    'paperless-files-': ('paperless_files', 'Paperless-Files', 'tar.gz'),
}


def _classify_backup(name):
    """Liefert (key, label, ext) für eine Backup-Datei oder None."""
    for prefix, meta in _BACKUP_PREFIXES.items():
        if name.startswith(prefix):
            return meta
    return None


def _human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return f'{n:.1f} {unit}'
        n /= 1024


def _scan_backups():
    """Sammelt alle Backup-Dateien gruppiert nach Typ."""
    backup_dir = Path(settings.BACKUP_DIR)
    groups = defaultdict(list)
    if not backup_dir.exists():
        return groups, backup_dir, 0
    total = 0
    for path in backup_dir.iterdir():
        if not path.is_file():
            continue
        meta = _classify_backup(path.name)
        if not meta:
            continue
        key, label, ext = meta
        stat = path.stat()
        groups[key].append({
            'name':  path.name,
            'label': label,
            'size':  stat.st_size,
            'size_h': _human_size(stat.st_size),
            'mtime': _dt.datetime.fromtimestamp(stat.st_mtime),
        })
        total += stat.st_size
    for key in groups:
        groups[key].sort(key=lambda e: e['mtime'], reverse=True)
    return groups, backup_dir, total


@_superuser_required
def backup_dashboard(request):
    """Übersicht: letzter Lauf je Typ + Quick-Action-Buttons."""
    from auditlog.models import AuditLogEntry

    groups, backup_dir, total_size = _scan_backups()

    cards = []
    for prefix, (key, label, ext) in _BACKUP_PREFIXES.items():
        entries = groups.get(key, [])
        latest = entries[0] if entries else None
        cards.append({
            'key':    key,
            'label':  label,
            'count':  len(entries),
            'latest': latest,
        })

    # Letzte Backup-Events aus Audit-Log
    recent_events = AuditLogEntry.objects.filter(
        action__in=[
            AuditLogEntry.ACTION_BACKUP,
            AuditLogEntry.ACTION_BACKUP_FAILED,
            AuditLogEntry.ACTION_RESTORE,
        ],
    ).order_by('-timestamp')[:15]

    trigger_buttons = [
        ('database',     'Datenbank',     'bi-database'),
        ('media',        'Media',         'bi-images'),
        ('paperless',    'Paperless',     'bi-archive'),
        ('cleanup',      'Rotation',      'bi-recycle'),
        ('offsite',      'Off-Site-Sync', 'bi-cloud-arrow-up'),
        ('restore_test', 'Restore-Test',  'bi-shield-check'),
    ]

    return render(request, 'services/backup_dashboard.html', {
        'cards':            cards,
        'recent_events':    recent_events,
        'backup_dir':       backup_dir,
        'total_size_h':     _human_size(total_size) if total_size else '0 B',
        'restic_configured': bool(os.environ.get('RESTIC_REPOSITORY')),
        'trigger_buttons':  trigger_buttons,
    })


@_superuser_required
def backup_list(request):
    """Tabelle aller Backups mit Lösch-Aktion."""
    groups, backup_dir, total_size = _scan_backups()
    sections = []
    for prefix, (key, label, ext) in _BACKUP_PREFIXES.items():
        entries = groups.get(key, [])
        sections.append({
            'key':     key,
            'label':   label,
            'entries': entries,
        })
    return render(request, 'services/backup_list.html', {
        'sections':     sections,
        'backup_dir':   backup_dir,
        'total_size_h': _human_size(total_size) if total_size else '0 B',
    })


@_superuser_required
def backup_settings(request):
    """SiteConfiguration für Backup-Zeiten und GFS-Aufbewahrung."""
    from .models import SiteConfiguration
    config = SiteConfiguration.get()
    errors = {}

    if request.method == 'POST':
        def _int(key, default, lo, hi):
            try:
                v = int(request.POST.get(key, default))
                if not (lo <= v <= hi):
                    raise ValueError
                return v
            except (ValueError, TypeError):
                errors[key] = True
                return default

        fields = {
            'backup_hour':           _int('backup_hour',           config.backup_hour,           0, 23),
            'backup_minute':         _int('backup_minute',         config.backup_minute,         0, 59),
            'backup_offsite_hour':   _int('backup_offsite_hour',   config.backup_offsite_hour,   0, 23),
            'backup_offsite_minute': _int('backup_offsite_minute', config.backup_offsite_minute, 0, 59),
            'backup_keep_weekly':    _int('backup_keep_weekly',    config.backup_keep_weekly,    0, 52),
            'backup_keep_monthly':   _int('backup_keep_monthly',   config.backup_keep_monthly,   0, 120),
        }
        if not errors:
            for field, value in fields.items():
                setattr(config, field, value)
            config.save(update_fields=list(fields.keys()))
            messages.success(request, 'Backup-Konfiguration gespeichert.')
            return redirect('services:backup_settings')
        messages.error(request, 'Bitte alle Felder korrekt ausfüllen.')

    return render(request, 'services/backup_settings.html', {
        'config':      config,
        'errors':      errors,
        'keep_daily':  int(os.environ.get('BACKUP_KEEP_DAILY', '7')),
        'alert_emails': os.environ.get('BACKUP_ALERT_EMAILS', ''),
        'restic_configured': bool(os.environ.get('RESTIC_REPOSITORY')),
    })


_BACKUP_TASKS = {
    'database':     ('services.backup_database',     'Datenbank-Backup'),
    'media':        ('services.backup_media',        'Media-Backup'),
    'paperless':    ('services.backup_paperless',    'Paperless-Backup'),
    'cleanup':      ('services.cleanup_old_backups', 'Backup-Rotation'),
    'offsite':      ('services.backup_offsite',      'Off-Site-Sync'),
    'restore_test': ('services.test_restore',        'Restore-Test'),
}


@_superuser_required
@require_POST
def backup_trigger(request, action):
    """Stellt eine Backup-Task in Celery ein (asynchron)."""
    from celery import current_app

    if action not in _BACKUP_TASKS:
        raise Http404('Unbekannte Backup-Aktion.')
    task_name, label = _BACKUP_TASKS[action]
    try:
        current_app.send_task(task_name)
        messages.success(
            request,
            f'{label} wurde gestartet. Ergebnis erscheint im Audit-Log und '
            f'auf dem Backup-Dashboard.',
        )
    except Exception as exc:
        messages.error(request, f'{label} konnte nicht gestartet werden: {exc}')
    return redirect(request.POST.get('next') or 'services:backup_dashboard')


@_superuser_required
@require_POST
def backup_delete(request, filename):
    """Löscht eine einzelne Backup-Datei nach Bestätigung."""
    from auditlog.models import AuditLogEntry

    # Sicherheitsprüfung: kein Pfad-Traversal, nur bekannte Prefixes
    if '/' in filename or '\\' in filename or filename.startswith('.'):
        raise Http404('Ungültiger Dateiname.')
    if not _classify_backup(filename):
        raise Http404('Datei ist kein Backup.')

    backup_dir = Path(settings.BACKUP_DIR)
    target = backup_dir / filename
    try:
        target_resolved = target.resolve(strict=True)
        if backup_dir.resolve() not in target_resolved.parents:
            raise Http404('Pfad außerhalb des Backup-Verzeichnisses.')
    except FileNotFoundError:
        raise Http404('Backup-Datei nicht gefunden.')

    size = target_resolved.stat().st_size
    target_resolved.unlink()
    AuditLogEntry.objects.create(
        user=request.user,
        action=AuditLogEntry.ACTION_DELETE,
        app_label='services',
        model_name='backup',
        model_verbose_name='Backup',
        object_id=filename,
        object_repr=f'Backup-Datei {filename} ({_human_size(size)}) gelöscht',
        changes={'deleted_via': 'web-ui', 'size_bytes': size},
    )
    messages.success(request, f'Backup {filename} wurde gelöscht.')
    return redirect('services:backup_list')


# ---------------------------------------------------------------------------
# SSO-Fehlerseite (von services.sso_adapter angesteuert)
# ---------------------------------------------------------------------------
SSO_ERROR_MESSAGES = {
    "no_email": (
        "Vom Identity-Provider wurde keine E-Mail-Adresse übermittelt. "
        "Bitte wenden Sie sich an die Ausbildungskoordination."
    ),
    "domain_not_allowed": (
        "Die übermittelte E-Mail-Adresse stammt nicht aus dem für diesen "
        "Identity-Provider hinterlegten Bereich."
    ),
    "no_local_account": (
        "Sie haben sich erfolgreich beim Identity-Provider angemeldet, "
        "für das Azubi-Portal ist jedoch kein Konto hinterlegt. "
        "Bitte wenden Sie sich an die Ausbildungskoordination."
    ),
    "multiple_local_accounts": (
        "Zu Ihrer E-Mail-Adresse existieren mehrere Konten. "
        "Bitte wenden Sie sich an die Ausbildungskoordination."
    ),
}

def sso_error(request):
    """Sprechende Fehlerseite für allauth-SSO-Probleme."""
    reason = request.GET.get("reason", "")
    message = SSO_ERROR_MESSAGES.get(
        reason,
        "Bei der Anmeldung über den Identity-Provider ist ein Fehler aufgetreten.",
    )
    return render(
        request,
        "registration/sso_error.html",
        {"message": message, "reason": reason},
        status=403,
    )


# ---------------------------------------------------------------------------
# Login-Seite mit SSO-Buttons + Smart-Redirect für SSO-User
# ---------------------------------------------------------------------------
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponseNotFound
from django.views.decorators.http import require_GET
from allauth.socialaccount.models import SocialApp, SocialAccount

LAST_IDP_COOKIE = "azubi_last_idp"


class AzubiLoginView(LoginView):
    """Login-Seite mit dynamischen Behörden-IdP-Buttons.

    Bei fehlgeschlagenem Lokal-Login eines SSO-Users wird die Seite mit
    einem klaren Hinweis auf den richtigen Provider neu gerendert, statt
    die generische Falsch-Anmeldedaten-Meldung zu zeigen.
    """
    template_name = "registration/login.html"

    def _idp_context(self):
        idps = list(
            SocialApp.objects
            .filter(provider="openid_connect")
            .order_by("name")
        )
        last_idp = self.request.COOKIES.get(LAST_IDP_COOKIE, "")
        if last_idp:
            # Zuletzt benutzten IdP nach vorne ziehen
            idps.sort(key=lambda a: a.provider_id != last_idp)
        return {
            "available_idps": idps,
            "last_idp_provider_id": last_idp,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self._idp_context())
        return ctx

    def form_valid(self, form):
        # Standard-Pfad: Passwort war korrekt, User wurde authentifiziert.
        # Wenn er 2FA aktiviert hat, NICHT direkt einloggen, sondern auf
        # die OTP-Eingabe umleiten und User-PK + Backend in der Session
        # zwischenspeichern.
        user = form.get_user()
        if _user_has_confirmed_otp(user):
            self.request.session[PENDING_2FA_USER_PK] = user.pk
            self.request.session[PENDING_2FA_BACKEND] = user.backend
            redirect_to = self.get_redirect_url() or settings.LOGIN_REDIRECT_URL
            self.request.session[PENDING_2FA_NEXT] = redirect_to
            from django.urls import reverse
            return HttpResponseRedirect(reverse("login_otp"))
        return super().form_valid(form)

    def form_invalid(self, form):
        # Smart-Redirect: Wenn der eingegebene Username einen SSO-User
        # identifiziert, zeigen wir statt "Anmeldedaten falsch" einen
        # spezifischen Hinweis auf seinen Provider.
        username = (self.request.POST.get("username") or "").strip()
        if username:
            user = User.objects.filter(username=username).first()
            if user is not None:
                sa = SocialAccount.objects.filter(user=user).first()
                if sa is not None:
                    app = SocialApp.objects.filter(
                        provider=sa.provider, provider_id=sa.provider
                    ).first() or SocialApp.objects.filter(provider=sa.provider).first()
                    ctx = self.get_context_data(form=form)
                    ctx.update({
                        "sso_required": True,
                        "sso_provider_name": app.name if app else "Identity-Provider",
                        "sso_provider_id": app.provider_id if app else "",
                    })
                    return self.render_to_response(ctx)
        return super().form_invalid(form)


@require_GET
def sso_start(request, provider_id):
    """Setzt Last-IdP-Cookie und triggert Auto-Submit-POST zum OIDC-Login.

    Statt direkt 302 zu /sso/oidc/<id>/login/ zu redirecten (allauth zeigt
    dort bei GET ein Interstitial), liefern wir ein winziges HTML mit einem
    Form, das per JavaScript sofort POST-submitted wird. Vorteile:

    * allauth's Login-CSRF-Schutz bleibt aktiv
    * Kein rohes Interstitial-Template mehr sichtbar
    * <noscript>-Fallback rendert einen klickbaren Knopf
    """
    if not SocialApp.objects.filter(
        provider="openid_connect", provider_id=provider_id
    ).exists():
        return HttpResponseNotFound()
    response = render(request, "registration/sso_redirect.html", {
        "post_target": f"/sso/oidc/{provider_id}/login/",
    })
    response.set_cookie(
        LAST_IDP_COOKIE, provider_id,
        max_age=60 * 60 * 24 * 365,  # 1 Jahr
        samesite="Lax",
        httponly=True,
        secure=not settings.DEBUG,
    )
    return response


# ---------------------------------------------------------------------------
# 2FA (TOTP + Recovery-Codes via django-otp) – optional, Self-Service
# ---------------------------------------------------------------------------
import base64
import io
import secrets

from django.contrib.auth import login as auth_login
from django_otp import devices_for_user, login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

PENDING_2FA_USER_PK = "pending_2fa_user_pk"
PENDING_2FA_BACKEND = "pending_2fa_backend"
PENDING_2FA_NEXT    = "pending_2fa_next"
RECOVERY_CODE_COUNT = 8
RECOVERY_CODE_LEN   = 10


def _user_has_confirmed_otp(user):
    """True, wenn der User mindestens ein bestätigtes OTP-Gerät hat."""
    return any(devices_for_user(user, confirmed=True))


def _verify_otp_token(user, token):
    """Prüft Token gegen alle bestätigten Geräte (TOTP + Static).

    Gibt das matchende Device zurück oder None.
    """
    token = (token or "").replace(" ", "").strip()
    if not token:
        return None
    for device in devices_for_user(user, confirmed=True):
        if device.verify_token(token):
            return device
    return None


def _qrcode_data_url(content):
    """PNG-Data-URL eines QR-Codes als base64 für direkte Einbettung."""
    import qrcode
    img = qrcode.make(content, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _generate_recovery_codes(user):
    """Verwirft bisherige Static-Tokens und legt neue Recovery-Codes an.

    Gibt die Codes als Liste zurück (nur einmal sichtbar – im Klartext werden
    sie danach in der DB nicht mehr abrufbar, da nur Hashes geprüft werden).
    """
    StaticDevice.objects.filter(user=user).delete()
    device = StaticDevice.objects.create(
        user=user, name="Recovery-Codes", confirmed=True,
    )
    codes = []
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    for _ in range(RECOVERY_CODE_COUNT):
        code = "".join(secrets.choice(alphabet) for _ in range(RECOVERY_CODE_LEN))
        StaticToken.objects.create(device=device, token=code)
        codes.append(code)
    return codes


@login_required
def mfa_setup(request):
    """2FA aktivieren: QR-Code anzeigen, ersten Code prüfen, bestätigen."""
    if _user_has_confirmed_otp(request.user):
        messages.info(request, "2FA ist bereits aktiviert. "
                               "Bitte zuerst deaktivieren, um neu einzurichten.")
        return redirect("services:mein_konto")

    # Bestehendes unbestätigtes Gerät wiederverwenden, sonst neu anlegen.
    # So überlebt der QR-Code mehrere Versuche, falls der User den Code
    # zunächst falsch tippt.
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(
            user=request.user, name="default", confirmed=False,
        )

    if request.method == "POST":
        token = request.POST.get("token", "")
        if device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            recovery_codes = _generate_recovery_codes(request.user)
            request.session["fresh_recovery_codes"] = recovery_codes
            messages.success(request, "Zwei-Faktor-Authentifizierung wurde aktiviert.")
            return redirect("services:mfa_recovery_codes")
        messages.error(request, "Code nicht gültig. Bitte erneut versuchen.")

    return render(request, "services/mfa_setup.html", {
        "qr_data_url": _qrcode_data_url(device.config_url),
        "secret": device.bin_key.hex(),  # Backup-Eingabe falls QR-Scan scheitert
    })


@login_required
@require_POST
def mfa_disable(request):
    """Alle 2FA-Geräte des Users löschen."""
    TOTPDevice.objects.filter(user=request.user).delete()
    StaticDevice.objects.filter(user=request.user).delete()
    messages.success(request, "Zwei-Faktor-Authentifizierung wurde deaktiviert.")
    return redirect("services:mein_konto")


@login_required
def mfa_recovery_codes(request):
    """Recovery-Codes anzeigen (frisch nach Setup) bzw. neu generieren."""
    if not _user_has_confirmed_otp(request.user):
        return redirect("services:mein_konto")

    if request.method == "POST" and request.POST.get("action") == "regenerate":
        codes = _generate_recovery_codes(request.user)
        request.session["fresh_recovery_codes"] = codes
        messages.success(request, "Neue Recovery-Codes wurden erzeugt. "
                                  "Die alten Codes sind ungültig.")
        return redirect("services:mfa_recovery_codes")

    codes = request.session.pop("fresh_recovery_codes", None)
    remaining = StaticToken.objects.filter(
        device__user=request.user, device__confirmed=True,
    ).count()
    return render(request, "services/mfa_recovery_codes.html", {
        "codes": codes,
        "remaining": remaining,
    })


def login_otp(request):
    """Zweistufiger Login: nach erfolgreichem Passwort-Submit landet hier,
    wer 2FA aktiviert hat.

    Holt den User-PK aus der Session, prüft den Token gegen TOTP/Static-Devices
    und führt bei Erfolg den eigentlichen django.auth-Login durch.
    """
    user_pk = request.session.get(PENDING_2FA_USER_PK)
    backend_path = request.session.get(PENDING_2FA_BACKEND)
    if not user_pk or not backend_path:
        return redirect("login")

    try:
        user = User.objects.get(pk=user_pk, is_active=True)
    except User.DoesNotExist:
        request.session.pop(PENDING_2FA_USER_PK, None)
        request.session.pop(PENDING_2FA_BACKEND, None)
        request.session.pop(PENDING_2FA_NEXT, None)
        return redirect("login")

    error = None
    if request.method == "POST":
        token = request.POST.get("token", "")
        device = _verify_otp_token(user, token)
        if device is not None:
            user.backend = backend_path
            auth_login(request, user)
            otp_login(request, device)
            # Falls ein Static-Token verwendet wurde: in der Static-Device-Logik
            # werden Tokens nach erfolgreicher Verwendung automatisch entfernt
            # – siehe django_otp.plugins.otp_static.models.StaticDevice.verify_token.
            next_url = request.session.pop(PENDING_2FA_NEXT, None) \
                       or settings.LOGIN_REDIRECT_URL
            request.session.pop(PENDING_2FA_USER_PK, None)
            request.session.pop(PENDING_2FA_BACKEND, None)
            return redirect(next_url)
        error = "Code nicht gültig. Bitte erneut versuchen."

    return render(request, "registration/login_otp.html", {"error": error})
