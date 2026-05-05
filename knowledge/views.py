# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für die Wissensdatenbank (Staff-Verwaltung und Portal-Ansicht für Nachwuchskräfte)."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models as db_models
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import KBCategory, KBDocument, VIS_ALL, VIS_JOB_PROFILE, VIS_COURSE, VIS_CAREER


def _require_leitung_or_referat(request):
    """Prüft ob der Nutzer Ausbildungsleitung oder Ausbildungsreferat ist."""
    from services.roles import is_training_director, is_training_office
    if not (is_training_director(request.user) or is_training_office(request.user)):
        raise PermissionDenied


# ── Staff-Verwaltung ──────────────────────────────────────────────────────────

@login_required
def kb_manage(request):
    """Verwaltungsoberfläche für Kategorien und Dokumente der Wissensdatenbank."""
    _require_leitung_or_referat(request)

    from course.models import JobProfile, Course, Career

    error = None

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Kategorien ────────────────────────────────────────────────────────
        if action == 'add_category':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Bitte einen Namen eingeben.'
            else:
                KBCategory.objects.create(
                    name=name,
                    icon=request.POST.get('icon', 'bi-folder').strip() or 'bi-folder',
                    order=int(request.POST.get('order', 0) or 0),
                    is_active=request.POST.get('is_active') == 'on',
                )
                messages.success(request, 'Kategorie wurde angelegt.')
                return redirect('knowledge:manage')

        elif action == 'edit_category':
            cat = get_object_or_404(KBCategory, pk=request.POST.get('category_id'))
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Bitte einen Namen eingeben.'
            else:
                cat.name = name
                cat.icon = request.POST.get('icon', 'bi-folder').strip() or 'bi-folder'
                cat.order = int(request.POST.get('order', 0) or 0)
                cat.is_active = request.POST.get('is_active') == 'on'
                cat.save()
                messages.success(request, 'Kategorie wurde gespeichert.')
                return redirect('knowledge:manage')

        # ── Dokumente ─────────────────────────────────────────────────────────
        elif action in ('add_document', 'edit_document'):
            is_edit = (action == 'edit_document')
            doc = (get_object_or_404(KBDocument, pk=request.POST.get('document_id'))
                   if is_edit else KBDocument())

            title = request.POST.get('title', '').strip()
            category_id = request.POST.get('category_id')
            uploaded_file = request.FILES.get('file')
            external_url = request.POST.get('external_url', '').strip()
            text_content = request.POST.get('content', '').strip()
            remove_file = request.POST.get('remove_file') == 'on'
            has_existing_file = is_edit and bool(doc.file) and not remove_file

            if not title:
                error = 'Bitte einen Titel eingeben.'
            elif not category_id:
                error = 'Bitte eine Kategorie wählen.'
            elif not (uploaded_file or external_url or text_content or has_existing_file):
                error = 'Bitte mindestens einen Inhalt angeben (Datei, URL oder Text).'
            else:
                # Hochgeladene Datei validieren (Typ und Größe)
                if uploaded_file:
                    from services.validators import validate_document
                    from django.core.exceptions import ValidationError
                    try:
                        validate_document(uploaded_file)
                    except ValidationError as e:
                        error = e.message
                        uploaded_file = None

                if not error:
                    doc.title = title
                    doc.category_id = category_id
                    doc.description = request.POST.get('description', '').strip()
                    doc.content = text_content
                    doc.external_url = external_url
                    doc.visibility = request.POST.get('visibility', VIS_ALL)
                    doc.target_job_profile_id = request.POST.get('target_job_profile') or None
                    doc.target_course_id = request.POST.get('target_course') or None
                    doc.target_career_id = request.POST.get('target_career') or None
                    doc.order = int(request.POST.get('order', 0) or 0)
                    doc.is_active = request.POST.get('is_active') == 'on'
                    if not is_edit:
                        doc.created_by = request.user

                    if uploaded_file:
                        if doc.file:
                            doc.file.delete(save=False)
                        doc.file = uploaded_file
                        doc.filename = ''  # wird in save() neu gesetzt
                    elif remove_file and doc.file:
                        doc.file.delete(save=False)
                        doc.file = None
                        doc.filename = ''

                    doc.save()
                    messages.success(request, 'Dokument wurde gespeichert.')
                    return redirect('knowledge:manage')

    categories = KBCategory.objects.prefetch_related(
        Prefetch(
            'documents',
            queryset=KBDocument.objects.select_related(
                'target_job_profile', 'target_course', 'target_career', 'created_by'
            ).order_by('order', 'title'),
        )
    )
    job_profiles = JobProfile.objects.order_by('job_profile')
    courses = Course.objects.order_by('-start_date')
    careers = Career.objects.order_by('description')

    return render(request, 'knowledge/manage.html', {
        'categories': categories,
        'job_profiles': job_profiles,
        'courses': courses,
        'careers': careers,
        'vis_all': VIS_ALL,
        'vis_job_profile': VIS_JOB_PROFILE,
        'vis_course': VIS_COURSE,
        'vis_career': VIS_CAREER,
        'error': error,
    })


@require_POST
@login_required
def kb_toggle_document(request, public_id):
    """Aktiviert oder deaktiviert ein Wissensdatenbank-Dokument."""
    _require_leitung_or_referat(request)
    doc = get_object_or_404(KBDocument, public_id=public_id)
    doc.is_active = not doc.is_active
    doc.save(update_fields=['is_active'])
    return redirect('knowledge:manage')


@require_POST
@login_required
def kb_delete_document(request, public_id):
    """Löscht ein Wissensdatenbank-Dokument inkl. zugehöriger Datei."""
    _require_leitung_or_referat(request)
    doc = get_object_or_404(KBDocument, public_id=public_id)
    if doc.file:
        doc.file.delete(save=False)
    doc.delete()
    messages.success(request, 'Dokument wurde gelöscht.')
    return redirect('knowledge:manage')


@require_POST
@login_required
def kb_delete_category(request, public_id):
    """Löscht eine Kategorie (nur wenn keine Dokumente mehr enthalten)."""
    _require_leitung_or_referat(request)
    cat = get_object_or_404(KBCategory, public_id=public_id)
    from django.db import IntegrityError
    try:
        cat.delete()
        messages.success(request, 'Kategorie wurde gelöscht.')
    except Exception:
        messages.error(request, 'Kategorie kann nicht gelöscht werden, solange noch Dokumente darin enthalten sind.')
    return redirect('knowledge:manage')


# ── Portal (Schüler) ──────────────────────────────────────────────────────────

@login_required
def portal_kb_list(request):
    """Wissensdatenbank-Übersicht für Nachwuchskräfte (gefiltert nach Sichtbarkeit)."""
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        from services.roles import is_training_director, is_training_office
        if is_training_director(request.user) or is_training_office(request.user):
            return redirect('knowledge:manage')
        raise PermissionDenied

    from student.models import Student
    student = Student.objects.select_related(
        'course__job_profile__career'
    ).get(pk=student.pk)

    categories = KBCategory.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            'documents',
            queryset=KBDocument.objects.filter(is_active=True).select_related(
                'target_job_profile', 'target_course', 'target_career'
            ).order_by('order', 'title'),
        )
    )

    sections = []
    for cat in categories:
        visible = [d for d in cat.documents.all() if d.is_visible_to_student(student)]
        if visible:
            sections.append({'category': cat, 'documents': visible})

    return render(request, 'knowledge/portal_list.html', {
        'student': student,
        'sections': sections,
    })


@login_required
def portal_kb_detail(request, public_id):
    """Detailansicht eines Wissensdatenbank-Dokuments für Nachwuchskräfte."""
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        raise PermissionDenied

    from student.models import Student
    student_obj = Student.objects.select_related(
        'course__job_profile__career'
    ).get(public_id=student.public_id)

    doc = get_object_or_404(
        KBDocument.objects.select_related('category'),
        public_id=public_id, is_active=True,
    )

    if not doc.is_visible_to_student(student_obj):
        raise PermissionDenied

    return render(request, 'knowledge/portal_detail.html', {'doc': doc})
