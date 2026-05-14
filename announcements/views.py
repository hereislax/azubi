# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Views für das Ankündigungs-Modul.

Enthält Verwaltungsansichten (Leitung / Referat) sowie Portal-Ansichten
für Nachwuchskräfte (Lesen, Bestätigen).
"""

import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Announcement, AnnouncementAttachment, AnnouncementRecipient,
    STATUS_DRAFT, STATUS_PUBLISHED,
    TARGET_ALL_STUDENTS, TARGET_COURSE, TARGET_JOB_PROFILE, TARGET_COORDINATION,
    TARGET_CAREER, TARGET_INDIVIDUAL, TARGET_CHOICES,
)

logger = logging.getLogger(__name__)


def _require_leitung_or_referat(request):
    """Prüft ob der Nutzer Ankündigungen verwalten darf (Leitung oder Referat mit Berechtigung)."""
    from services.roles import is_training_director, is_training_office, get_training_office_profile
    if is_training_director(request.user):
        return
    if is_training_office(request.user):
        training_office_profile = get_training_office_profile(request.user)
        if training_office_profile and training_office_profile.can_manage_announcements:
            return
    raise PermissionDenied


def _get_student_or_403(request):
    student = getattr(request.user, 'student_profile', None)
    if student is None:
        raise PermissionDenied
    return student


# ── Verwaltungsansichten (Leitung / Referat) ──────────────────────────────────

@login_required
def announcement_list(request):
    _require_leitung_or_referat(request)
    qs = (
        Announcement.objects
        .select_related('sender', 'target_course', 'target_job_profile')
        .order_by('-created_at')
    )
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'announcements/list.html', {
        'page_obj': page,
        'status_filter': status_filter,
    })


@login_required
def announcement_pending_approvals(request):
    """Listet alle Ankündigungen, die auf Freigabe durch die Ausbildungsleitung warten."""
    from services.roles import is_training_director
    if not is_training_director(request.user):
        raise PermissionDenied

    from django.contrib.contenttypes.models import ContentType
    from workflow.models import WorkflowInstance, INSTANCE_STATUS_IN_PROGRESS

    ct = ContentType.objects.get_for_model(Announcement)
    instances = list(
        WorkflowInstance.objects
        .filter(target_ct=ct, status=INSTANCE_STATUS_IN_PROGRESS,
                definition__code='announcement_publish')
        .select_related('current_step', 'initiator', 'definition')
        .order_by('-started_at')
    )

    # Zielobjekte vorladen
    ann_ids = [i.target_id for i in instances]
    anns = {
        a.pk: a for a in
        Announcement.objects
        .filter(pk__in=ann_ids)
        .select_related('sender')
    }

    rows = []
    for inst in instances:
        ann = anns.get(inst.target_id)
        if ann is None:
            continue
        rows.append({
            'instance':     inst,
            'announcement': ann,
        })

    return render(request, 'announcements/pending_approvals.html', {
        'rows': rows,
    })


@login_required
def announcement_approve(request, public_id):
    """Genehmigt oder lehnt eine zur Freigabe vorgelegte Ankündigung ab."""
    from services.roles import is_training_director
    from workflow.engine import (
        get_instance_for, perform_action, can_act, WorkflowError,
        ACTION_APPROVE, ACTION_REJECT,
    )
    if not is_training_director(request.user):
        raise PermissionDenied

    announcement = get_object_or_404(Announcement, public_id=public_id)
    instance = get_instance_for(announcement)
    if not instance or not instance.is_active:
        messages.error(request, 'Für diese Ankündigung läuft kein Freigabe-Workflow.')
        return redirect('announcements:detail', public_id=public_id)

    if not can_act(instance, request.user):
        raise PermissionDenied

    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()
        try:
            if action == 'approve':
                perform_action(instance, actor=request.user,
                               action=ACTION_APPROVE, comment=comment)
                messages.success(request, 'Ankündigung freigegeben und veröffentlicht.')
            elif action == 'reject':
                if not comment:
                    messages.error(request, 'Bei Ablehnung bitte eine Begründung angeben.')
                    return redirect('announcements:approve', public_id=public_id)
                perform_action(instance, actor=request.user,
                               action=ACTION_REJECT, comment=comment)
                messages.success(request, 'Ankündigung an Verfasser:in zurückgegeben.')
            else:
                messages.error(request, 'Unbekannte Aktion.')
        except WorkflowError as exc:
            messages.error(request, f'Aktion nicht möglich: {exc}')
        return redirect('announcements:pending_approvals')

    return render(request, 'announcements/approve.html', {
        'announcement': announcement,
        'instance':     instance,
    })


@login_required
def announcement_create(request):
    _require_leitung_or_referat(request)
    return _announcement_form(request, announcement=None)


@login_required
def announcement_edit(request, public_id):
    _require_leitung_or_referat(request)
    announcement = get_object_or_404(Announcement, public_id=public_id)
    if announcement.status == STATUS_PUBLISHED:
        messages.error(request, 'Veröffentlichte Ankündigungen können nicht mehr bearbeitet werden.')
        return redirect('announcements:list')
    return _announcement_form(request, announcement=announcement)


def _announcement_form(request, announcement):
    from course.models import Course, JobProfile, Career
    from instructor.models import TrainingCoordination
    from student.models import Student

    courses        = Course.objects.order_by('-start_date')
    job_profiles   = JobProfile.objects.order_by('job_profile')
    training_coordinations = TrainingCoordination.objects.order_by('name')
    careers        = Career.objects.order_by('description')
    all_students   = (
        Student.objects
        .filter(anonymized_at__isnull=True)
        .select_related('course')
        .order_by('last_name', 'first_name')
    )

    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        body        = request.POST.get('body', '').strip()
        target_type = request.POST.get('target_type', TARGET_ALL_STUDENTS)
        requires_ack = request.POST.get('requires_acknowledgement') == '1'
        send_email   = request.POST.get('send_email') == '1'

        target_course        = None
        target_job_profile   = None
        target_coordination  = None
        target_career        = None
        target_student_pks   = request.POST.getlist('target_student_pks')
        if target_type == TARGET_COURSE:
            pk = request.POST.get('target_course')
            target_course = Course.objects.filter(pk=pk).first() if pk else None
        elif target_type == TARGET_JOB_PROFILE:
            pk = request.POST.get('target_job_profile')
            target_job_profile = JobProfile.objects.filter(pk=pk).first() if pk else None
        elif target_type == TARGET_COORDINATION:
            pk = request.POST.get('target_coordination')
            target_coordination = TrainingCoordination.objects.filter(pk=pk).first() if pk else None
        elif target_type == TARGET_CAREER:
            pk = request.POST.get('target_career')
            target_career = Career.objects.filter(pk=pk).first() if pk else None

        if not title:
            messages.error(request, 'Bitte einen Titel eingeben.')
        elif not body or body == '<p><br></p>':
            messages.error(request, 'Bitte einen Inhalt eingeben.')
        else:
            if announcement is None:
                announcement = Announcement(sender=request.user)
            announcement.title               = title
            announcement.body                = body
            announcement.target_type         = target_type
            announcement.target_course       = target_course
            announcement.target_job_profile  = target_job_profile
            announcement.target_coordination = target_coordination
            announcement.target_career       = target_career
            announcement.requires_acknowledgement = requires_ack
            announcement.send_email          = send_email
            announcement.save()
            if target_type == TARGET_INDIVIDUAL:
                announcement.target_students.set(
                    Student.objects.filter(pk__in=target_student_pks)
                )

            # Neu hochgeladene Datei-Anhänge verarbeiten
            for f in request.FILES.getlist('attachments'):
                att = AnnouncementAttachment(
                    announcement=announcement,
                    file=f,
                    filename=f.name,
                )
                att.save()

            # Löschungen von Anhängen verarbeiten
            delete_ids = request.POST.getlist('delete_attachment')
            if delete_ids:
                AnnouncementAttachment.objects.filter(
                    announcement=announcement, pk__in=delete_ids
                ).delete()

            action = request.POST.get('action', 'save')
            if action == 'publish':
                published, info = _publish_or_request_approval(announcement, request.user)
                if published:
                    messages.success(request, info)
                    return redirect('announcements:detail', public_id=announcement.public_id)
                messages.info(request, info)
                return redirect('announcements:detail', public_id=announcement.public_id)

            messages.success(request, 'Ankündigung gespeichert.')
            return redirect('announcements:edit', public_id=announcement.public_id)

    selected_student_pks = set(
        announcement.target_students.values_list('pk', flat=True)
    ) if announcement and announcement.pk else set()

    return render(request, 'announcements/form.html', {
        'announcement':        announcement,
        'courses':             courses,
        'job_profiles':        job_profiles,
        'training_coordinations': training_coordinations,
        'careers':             careers,
        'all_students':        all_students,
        'selected_student_pks': selected_student_pks,
        'target_choices':      TARGET_CHOICES,
        'TARGET_ALL_STUDENTS': TARGET_ALL_STUDENTS,
        'TARGET_COURSE':       TARGET_COURSE,
        'TARGET_JOB_PROFILE':  TARGET_JOB_PROFILE,
        'TARGET_COORDINATION': TARGET_COORDINATION,
        'TARGET_CAREER':       TARGET_CAREER,
        'TARGET_INDIVIDUAL':   TARGET_INDIVIDUAL,
    })


@login_required
def announcement_detail(request, public_id):
    _require_leitung_or_referat(request)
    announcement = get_object_or_404(
        Announcement.objects.select_related('sender', 'target_course', 'target_job_profile'),
        public_id=public_id,
    )
    recipients = list(
        announcement.recipients
        .select_related('user')
        .order_by('user__last_name', 'user__first_name')
    )
    read_count   = sum(1 for r in recipients if r.read_at)
    ack_count    = sum(1 for r in recipients if r.acknowledged_at)
    unread_count = len(recipients) - read_count
    return render(request, 'announcements/detail.html', {
        'announcement': announcement,
        'recipients':   recipients,
        'read_count':   read_count,
        'ack_count':    ack_count,
        'unread_count': unread_count,
    })


@login_required
@require_POST
def announcement_publish(request, public_id):
    _require_leitung_or_referat(request)
    announcement = get_object_or_404(Announcement, public_id=public_id, status=STATUS_DRAFT)
    published, info = _publish_or_request_approval(announcement, request.user)
    if published:
        messages.success(request, info)
    else:
        messages.info(request, info)
    return redirect('announcements:detail', public_id=public_id)


@login_required
@require_POST
def announcement_delete(request, public_id):
    _require_leitung_or_referat(request)
    announcement = get_object_or_404(Announcement, public_id=public_id, status=STATUS_DRAFT)
    announcement.delete()
    messages.success(request, 'Entwurf gelöscht.')
    return redirect('announcements:list')


def _send_announcement_emails(announcement):
    """Stellt den E-Mail-Versand als Celery-Task in die Redis-Queue."""
    from .tasks import send_announcement_emails
    send_announcement_emails.delay(announcement.pk)
    return len(announcement.get_target_emails())


def _do_publish(announcement):
    """Tatsächliche Veröffentlichung — wird direkt oder vom Workflow-Hook aufgerufen."""
    if announcement.status == STATUS_PUBLISHED:
        return 0
    announcement.publish()
    announcement.create_recipients()
    sent = 0
    if announcement.send_email:
        sent = _send_announcement_emails(announcement)
    return sent


def _publish_or_request_approval(announcement, user):
    """Veröffentlicht direkt, oder startet einen Freigabe-Workflow.

    Liefert ``(published: bool, message: str)``. Wenn ``published`` False ist,
    wartet die Ankündigung auf Freigabe durch die Ausbildungsleitung.
    """
    from services.roles import is_training_director
    from workflow.engine import (
        start_workflow, get_instance_for, WorkflowError,
        INSTANCE_STATUS_APPROVED, INSTANCE_STATUS_IN_PROGRESS,
    )

    # Ausbildungsleitung darf immer ohne Workflow veröffentlichen
    if is_training_director(user):
        sent = _do_publish(announcement)
        return True, _publish_success_msg(announcement, sent)

    # Workflow starten — Pre-Condition entscheidet, ob Freigabe nötig
    existing = get_instance_for(announcement)
    if existing and existing.is_active:
        return False, ('Diese Ankündigung wartet bereits auf Freigabe '
                       'durch die Ausbildungsleitung.')

    try:
        instance = start_workflow('announcement_publish',
                                   target=announcement, initiator=user)
    except WorkflowError as exc:
        logger.warning('Workflow „announcement_publish" nicht startbar: %s', exc)
        # Fallback: ohne Workflow direkt veröffentlichen (Definition fehlt)
        sent = _do_publish(announcement)
        return True, _publish_success_msg(announcement, sent)

    if instance.status == INSTANCE_STATUS_APPROVED:
        # Pre-Condition nicht erfüllt → wurde sofort auto-approved und Hook hat publiziert
        announcement.refresh_from_db()
        sent_count = len(announcement.get_target_emails()) if announcement.send_email else 0
        return True, _publish_success_msg(announcement, sent_count)

    if instance.status == INSTANCE_STATUS_IN_PROGRESS:
        return False, ('Ankündigung gespeichert und zur Freigabe an die '
                       'Ausbildungsleitung gesendet.')

    return False, 'Ankündigung gespeichert, Workflow-Status unbekannt.'


def _publish_success_msg(announcement, sent_count):
    msg = 'Ankündigung veröffentlicht.'
    if announcement.send_email:
        msg += f' E-Mail an {sent_count} Empfänger versendet.'
    return msg


# ── Portal-Ansichten (NK) ─────────────────────────────────────────────────────

@login_required
def portal_announcement_list(request):
    _get_student_or_403(request)
    qs = (
        AnnouncementRecipient.objects
        .filter(user=request.user, announcement__status=STATUS_PUBLISHED)
        .select_related('announcement__sender')
        .order_by('-announcement__published_at')
    )
    unread_count = qs.filter(read_at__isnull=True).count()
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'announcements/portal_list.html', {
        'page_obj':    page,
        'unread_count': unread_count,
    })


@login_required
def portal_announcement_detail(request, pk):
    _get_student_or_403(request)
    recipient = get_object_or_404(
        AnnouncementRecipient.objects.select_related(
            'announcement__sender',
            'announcement__target_course',
        ),
        announcement_id=pk,
        user=request.user,
        announcement__status=STATUS_PUBLISHED,
    )
    if not recipient.read_at:
        recipient.read_at = timezone.now()
        recipient.save(update_fields=['read_at'])

    return render(request, 'announcements/portal_detail.html', {
        'recipient':    recipient,
        'announcement': recipient.announcement,
    })


@login_required
@require_POST
def portal_acknowledge(request, pk):
    _get_student_or_403(request)
    recipient = get_object_or_404(
        AnnouncementRecipient,
        announcement_id=pk,
        user=request.user,
        announcement__status=STATUS_PUBLISHED,
    )
    if not recipient.acknowledged_at:
        recipient.acknowledged_at = timezone.now()
        if not recipient.read_at:
            recipient.read_at = timezone.now()
        recipient.save(update_fields=['acknowledged_at', 'read_at'])
    messages.success(request, 'Bestätigt.')
    return redirect('portal:announcement_detail', pk=pk)
