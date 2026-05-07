# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""E-Mail- und Portal-Benachrichtigungen für Ausbildungskoordinationen, Praxistutoren und Nachwuchskräfte."""
import logging

logger = logging.getLogger(__name__)


def is_email_enabled(user, key: str) -> bool:
    """
    Gibt True zurück, wenn der Benutzer E-Mails für den gegebenen
    Notification-Key empfangen möchte (Standard: ja).
    user darf None sein – dann wird True zurückgegeben.
    """
    if user is None:
        return True
    try:
        from services.models import UserNotificationPreference
        pref = UserNotificationPreference.objects.get(user=user)
        return key not in (pref.disabled_keys or [])
    except Exception:
        return True


def notify_instructor_of_assignment(request, assignment):
    """Benachrichtigt den zugewiesenen Praxistutor über die neue Nachwuchskraft.

    Hängt eine ganztägige iCal-Termineinladung (METHOD:REQUEST) an, damit der
    Einsatzzeitraum automatisch im Outlook-Kalender erscheint.
    """
    from django.conf import settings
    from django.contrib import messages as django_messages
    from services.email import send_mail
    from services.models import NotificationTemplate
    from services.calendar import (
        build_event_ics,
        ics_attachment_tuple,
        stable_uid,
        daterange_end_exclusive,
        METHOD_REQUEST,
    )

    instructor = assignment.instructor
    if not instructor:
        logger.warning('notify_instructor_of_assignment: Kein Praxistutor gesetzt (pk=%s)', assignment.pk)
        return
    if not instructor.email:
        logger.warning('notify_instructor_of_assignment: Praxistutor %s hat keine E-Mail', instructor)
        django_messages.warning(request, f'Praxistutor „{instructor}" hat keine E-Mail-Adresse – keine Benachrichtigung möglich.')
        return

    student = assignment.student
    unit = assignment.unit
    block = assignment.schedule_block
    detail_url = request.build_absolute_uri(f'/student/{student.pk}/')

    subject, body = NotificationTemplate.render('instructor_assignment', {
        'anrede':           f'Guten Tag {instructor.first_name} {instructor.last_name},',
        'student_vorname':  student.first_name,
        'student_nachname': student.last_name,
        'einheit':          unit.name,
        'von':              assignment.start_date.strftime('%d.%m.%Y'),
        'bis':              assignment.end_date.strftime('%d.%m.%Y'),
        'block':            block.name,
        'detail_url':       detail_url,
    })

    attachments = None
    try:
        ics_bytes = build_event_ics(
            uid=stable_uid(assignment, 'einsatz'),
            summary=f'Stationseinsatz: {student.first_name} {student.last_name} – {unit.name}',
            start=assignment.start_date,
            end=daterange_end_exclusive(assignment.end_date),
            description=(
                f'Block: {block.name}\n'
                f'Nachwuchskraft: {student.first_name} {student.last_name}\n'
                f'Organisationseinheit: {unit.name}\n\n'
                f'Details: {detail_url}'
            ),
            location=unit.name,
            organizer_email=settings.DEFAULT_FROM_EMAIL or None,
            attendee_emails=[instructor.email],
            sequence=assignment.notification_sequence,
            method=METHOD_REQUEST,
            url=detail_url,
        )
        attachments = [ics_attachment_tuple('einsatz.ics', ics_bytes, METHOD_REQUEST)]
    except Exception as exc:
        logger.warning('iCal-Anhang für Einsatz pk=%s konnte nicht erzeugt werden: %s', assignment.pk, exc)

    try:
        send_mail(
            subject=subject,
            body_text=body,
            recipient_list=[instructor.email],
            attachments=attachments,
        )
        logger.info('Benachrichtigung an Praxistutor %s gesendet (Einsatz pk=%s)', instructor.email, assignment.pk)
    except Exception as exc:
        logger.error('Benachrichtigung an Praxistutor %s fehlgeschlagen: %s', instructor.email, exc)
        django_messages.warning(
            request,
            f'Einsatz gespeichert, aber Benachrichtigung an „{instructor}" konnte nicht gesendet werden: {exc}',
        )


def notify_creator_of_decision(request, assignment):
    """
    Benachrichtigt die Person, die den Praktikumseinsatz angelegt hat,
    über die Entscheidung der Ausbildungskoordination (Annahme oder Ablehnung).
    Link führt zum Praktikumskalender des betreffenden Blocks.
    """
    from services.email import send_mail
    from services.models import NotificationTemplate

    creator = assignment.created_by
    if not creator or not creator.email:
        logger.info(
            'notify_creator_of_decision: Kein Ersteller oder keine E-Mail für Einsatz pk=%s',
            assignment.pk,
        )
        return

    student = assignment.student
    unit = assignment.unit
    block = assignment.schedule_block
    calendar_url = request.build_absolute_uri(
        f'/course/{block.course_id}/ablaufplan/{block.pk}/praktikum/'
    )

    key = 'assignment_approved' if assignment.status == 'approved' else 'assignment_rejected'
    if not is_email_enabled(creator, key):
        logger.info('Entscheidungs-Benachrichtigung übersprungen (deaktiviert): %s', creator.email)
        return

    subject, body = NotificationTemplate.render(key, {
        'vorname':          creator.first_name,
        'nachname':         creator.last_name,
        'student_vorname':  student.first_name,
        'student_nachname': student.last_name,
        'einheit':          unit.name,
        'von':              assignment.start_date.strftime('%d.%m.%Y'),
        'bis':              assignment.end_date.strftime('%d.%m.%Y'),
        'block':            block.name,
        'detail_url':       calendar_url,
        'ablehnungsgrund':  assignment.rejection_reason,
    })

    # Bei Annahme: Termin als iCal-REQUEST anhängen, damit der Antragsteller
    # ihn automatisch in den Outlook-Kalender übernehmen kann.
    attachments = None
    if assignment.status == 'approved':
        from django.conf import settings
        from services.calendar import (
            build_event_ics,
            ics_attachment_tuple,
            stable_uid,
            daterange_end_exclusive,
            METHOD_REQUEST,
        )
        try:
            ics_bytes = build_event_ics(
                uid=stable_uid(assignment, 'einsatz'),
                summary=f'Stationseinsatz: {student.first_name} {student.last_name} – {unit.name}',
                start=assignment.start_date,
                end=daterange_end_exclusive(assignment.end_date),
                description=(
                    f'Block: {block.name}\n'
                    f'Nachwuchskraft: {student.first_name} {student.last_name}\n'
                    f'Organisationseinheit: {unit.name}\n\n'
                    f'Details: {calendar_url}'
                ),
                location=unit.name,
                organizer_email=settings.DEFAULT_FROM_EMAIL or None,
                attendee_emails=[creator.email],
                sequence=assignment.notification_sequence,
                method=METHOD_REQUEST,
                url=calendar_url,
            )
            attachments = [ics_attachment_tuple('einsatz.ics', ics_bytes, METHOD_REQUEST)]
        except Exception as exc:
            logger.warning('iCal-Anhang für Einsatz-Annahme pk=%s konnte nicht erzeugt werden: %s', assignment.pk, exc)

    try:
        send_mail(
            subject=subject,
            body_text=body,
            recipient_list=[creator.email],
            attachments=attachments,
        )
        logger.info(
            'Entscheidungs-Benachrichtigung an %s gesendet (Einsatz pk=%s, Status=%s)',
            creator.email, assignment.pk, assignment.status,
        )
    except Exception as exc:
        logger.warning(
            'Entscheidungs-Benachrichtigung an %s fehlgeschlagen: %s',
            creator.email, exc,
        )

    # Interne Benachrichtigung für den Ersteller
    try:
        from services.models import create_notification
        block = assignment.schedule_block
        calendar_url = f'/kurs/{block.course_id}/ablaufplan/{block.pk}/praktikum/'
        if assignment.status == 'approved':
            create_notification(
                creator,
                message=f'Einsatz angenommen: {assignment.student.first_name} {assignment.student.last_name} – {assignment.unit.name}',
                link=calendar_url,
                icon='bi-check-circle',
                category='Einsatz',
            )
        else:
            create_notification(
                creator,
                message=f'Einsatz abgelehnt: {assignment.student.first_name} {assignment.student.last_name} – {assignment.unit.name}',
                link=calendar_url,
                icon='bi-x-circle',
                category='Einsatz',
            )
    except Exception:
        pass

def _office_recipients_with_users():
    """Liefert ein Tupel (User-Liste, E-Mail-Liste) für Ausbildungsreferat-Mitglieder."""
    from django.contrib.auth.models import User
    users = list(User.objects.filter(groups__name='ausbildungsreferat', is_active=True).distinct())
    emails = [u.email for u in users if u.email]
    return users, emails


def notify_training_office_of_assignment_decision(request, assignment):
    """Informiert das Ausbildungsreferat ueber Annahme/Ablehnung eines Einsatzes."""
    from services.email import send_mail
    from services.models import NotificationTemplate, create_notification

    users, emails = _office_recipients_with_users()
    if not users:
        return

    student = assignment.student
    unit = assignment.unit
    block = assignment.schedule_block
    detail_url = request.build_absolute_uri(f'/student/{student.pk}/')
    is_approved = assignment.status == 'approved'

    subject, body = NotificationTemplate.render('assignment_decision_for_office', {
        'entscheidung':     'angenommen' if is_approved else 'abgelehnt',
        'student_vorname':  student.first_name,
        'student_nachname': student.last_name,
        'einheit':          unit.name,
        'von':              assignment.start_date.strftime('%d.%m.%Y'),
        'bis':              assignment.end_date.strftime('%d.%m.%Y'),
        'block':            block.name,
        'ablehnungsgrund':  assignment.rejection_reason,
        'detail_url':       detail_url,
    })

    icon = 'bi-check-circle' if is_approved else 'bi-x-circle'
    short_label = 'angenommen' if is_approved else 'abgelehnt'
    for user in users:
        if not is_email_enabled(user, 'assignment_decision_for_office'):
            continue
        create_notification(
            user,
            message=f'Einsatz {short_label}: {student.first_name} {student.last_name} – {unit.name}',
            link=f'/student/{student.pk}/',
            icon=icon,
            category='Einsatz',
        )

    if emails:
        try:
            send_mail(subject=subject, body_text=body, recipient_list=emails)
        except Exception as exc:
            logger.warning('Mail an Ausbildungsreferat fehlgeschlagen: %s', exc)


def _staff_users(group_names):
    from django.contrib.auth.models import User
    return list(
        User.objects.filter(groups__name__in=list(group_names), is_active=True)
        .distinct()
    )


def notify_change_request_submitted(request, change_request):
    """Benachrichtigt die Ausbildungsleitung über einen neuen Änderungsantrag."""
    from django.urls import reverse
    from services.email import send_mail
    from services.models import NotificationTemplate, create_notification

    a = change_request.assignment
    review_url = request.build_absolute_uri(
        reverse('instructor:change_request_review',
                kwargs={'change_request_public_id': change_request.public_id})
    )
    requester = change_request.requested_by
    requester_name = (
        f'{requester.first_name} {requester.last_name}'.strip() if requester else 'Unbekannt'
    ) or (requester.username if requester else 'Unbekannt')

    subject, body = NotificationTemplate.render('change_request_submitted', {
        'aenderungstyp':    change_request.get_change_type_display(),
        'antragsteller':    requester_name,
        'student_vorname':  a.student.first_name,
        'student_nachname': a.student.last_name,
        'einheit':          a.unit.name,
        'zusammenfassung':  change_request.summary(),
        'begruendung':      change_request.reason,
        'detail_url':       review_url,
    })

    leitung = _staff_users(['ausbildungsleitung'])
    for user in leitung:
        create_notification(
            user,
            message=f'Änderungsantrag: {change_request.get_change_type_display()} – '
                    f'{a.student.first_name} {a.student.last_name}',
            link=reverse('instructor:change_request_review',
                         kwargs={'change_request_public_id': change_request.public_id}),
            icon='bi-pencil-square',
            category='Änderungsantrag',
        )

    emails = [u.email for u in leitung
              if u.email and is_email_enabled(u, 'change_request_submitted')]
    if emails:
        try:
            send_mail(subject=subject, body_text=body, recipient_list=emails)
        except Exception as exc:
            logger.warning('Mail an Ausbildungsleitung (Änderungsantrag) fehlgeschlagen: %s', exc)


def notify_change_request_decided(request, change_request):
    """Informiert Antragsteller, Koordination und Ausbildungsreferat ueber die Entscheidung."""
    from services.email import send_mail
    from services.models import NotificationTemplate, create_notification

    a = change_request.assignment
    detail_url = request.build_absolute_uri(f'/student/{a.student.pk}/')
    is_approved = change_request.status == 'approved'
    template_key = 'change_request_approved' if is_approved else 'change_request_rejected'
    icon = 'bi-check-circle' if is_approved else 'bi-x-circle'
    short = 'genehmigt' if is_approved else 'abgelehnt'

    # Empfänger: Antragsteller + alle Koordinations-User + Ausbildungsreferat
    recipients_users = []
    if change_request.requested_by:
        recipients_users.append(change_request.requested_by)
    recipients_users.extend(_staff_users(['ausbildungskoordination', 'ausbildungsreferat']))
    # De-duplizieren ueber pk
    seen = set()
    deduped = []
    for u in recipients_users:
        if u.pk in seen:
            continue
        seen.add(u.pk)
        deduped.append(u)

    short_msg = (
        f'Änderungsantrag {short}: {change_request.get_change_type_display()} – '
        f'{a.student.first_name} {a.student.last_name}'
    )
    for u in deduped:
        create_notification(
            u,
            message=short_msg,
            link=f'/student/{a.student.pk}/',
            icon=icon,
            category='Änderungsantrag',
        )

    anrede_default = 'Guten Tag,'
    payload_common = {
        'aenderungstyp':    change_request.get_change_type_display(),
        'student_vorname':  a.student.first_name,
        'student_nachname': a.student.last_name,
        'einheit':          a.unit.name if a.unit_id else '–',
        'zusammenfassung':  change_request.summary(),
        'detail_url':       detail_url,
    }
    if not is_approved:
        payload_common['ablehnungsgrund'] = change_request.rejection_reason

    for u in deduped:
        if not u.email or not is_email_enabled(u, template_key):
            continue
        anrede = (
            f'Guten Tag {u.first_name} {u.last_name},'.strip()
            if u.first_name or u.last_name else anrede_default
        )
        subject, body = NotificationTemplate.render(template_key, {
            **payload_common, 'anrede': anrede,
        })
        try:
            send_mail(subject=subject, body_text=body, recipient_list=[u.email])
        except Exception as exc:
            logger.warning('Entscheidungs-Mail (Änderungsantrag) an %s fehlgeschlagen: %s',
                           u.email, exc)


def notify_instructor_confirmed(instructor, detail_url, creator=None):
    """
    Sendet das Bestellungsschreiben (Word-Vorlage → PDF via Paperless) an den
    Praxistutor und eine separate Benachrichtigung an die zuständige
    Ausbildungskoordination. Beide Mails enthalten die PDF als Anhang.
    """
    from services.email import send_mail
    from services.models import NotificationTemplate

    unit = instructor.unit
    berufsbilder = ', '.join(str(jp) for jp in instructor.job_profiles.all()) or '–'

    pdf_bytes, pdf_filename = _generate_instructor_order_pdf(instructor, berufsbilder, creator=creator)
    attachments = [(pdf_filename, pdf_bytes, 'application/pdf')] if pdf_bytes else None

    anrede = f'Guten Tag {instructor.first_name} {instructor.last_name},'
    subject, body = NotificationTemplate.render('instructor_confirmed', {
        'anrede':       anrede,
        'vorname':      instructor.first_name,
        'nachname':     instructor.last_name,
        'einheit':      unit.name if unit else '–',
        'berufsbilder': berufsbilder,
        'detail_url':   detail_url,
    })

    if instructor.email:
        try:
            send_mail(
                subject=subject,
                body_text=body,
                recipient_list=[instructor.email],
                attachments=attachments,
            )
            logger.info('Bestellungsschreiben an %s gesendet (Instructor pk=%s)', instructor.email, instructor.pk)
        except Exception as exc:
            logger.warning('Bestellungsschreiben an %s fehlgeschlagen: %s', instructor.email, exc)

    # Zustaendige Ausbildungskoordinationen benachrichtigen
    if unit:
        coordinations = _get_coordinations_for_unit(unit)
        seen: set[str] = set()
        for coordination in coordinations:
            if coordination.functional_email:
                recipients = [(coordination.functional_email, 'Guten Tag,')]
            else:
                recipients = [
                    (m.email, f'Guten Tag {m.first_name} {m.last_name},')
                    for m in coordination.members.all() if m.email
                ]
            for recipient, k_anrede in recipients:
                if not recipient or recipient in seen:
                    continue
                seen.add(recipient)
                k_subject, k_body = NotificationTemplate.render('instructor_confirmed_coordinator', {
                    'anrede':            k_anrede,
                    'vorname':           instructor.first_name,
                    'nachname':          instructor.last_name,
                    'praxistutor_email': instructor.email or '–',
                    'einheit':           unit.name,
                    'berufsbilder':      berufsbilder,
                    'detail_url':        detail_url,
                })
                try:
                    send_mail(
                        subject=k_subject,
                        body_text=k_body,
                        recipient_list=[recipient],
                        attachments=attachments,
                    )
                except Exception as exc:
                    logger.warning('Koordinations-Benachrichtigung an %s fehlgeschlagen: %s', recipient, exc)


def _generate_instructor_order_pdf(instructor, berufsbilder, creator=None):
    """
    Rendert die aktive InstructorOrderTemplate (.docx) mit Praxistutor-Kontext,
    lädt das Dokument zu Paperless hoch (document_type „Bestellung Praxistutor")
    und holt die konvertierte PDF zurück. Gibt (pdf_bytes, filename) oder (None, None) zurück.
    """
    try:
        from instructor.models import InstructorOrderTemplate
        from services.paperless import PaperlessService
        from document.contexts import instructor_context, creator_context, meta_context
        from document.render import render_docx, upload_to_paperless
    except Exception as exc:
        logger.error('Bestellungs-PDF: Import fehlgeschlagen: %s', exc)
        return None, None

    template_obj = (
        InstructorOrderTemplate.objects
        .filter(is_active=True)
        .order_by('-uploaded_at')
        .first()
    )
    if template_obj is None:
        logger.info('Bestellungs-PDF: Keine aktive Vorlage hinterlegt – Mail ohne Anhang.')
        return None, None

    ctx = {
        **instructor_context(instructor),
        **creator_context(creator),
        **meta_context(),
        'berufsbilder': berufsbilder,
    }

    try:
        file_bytes = render_docx(template_obj.template_file.path, ctx)
    except Exception as exc:
        logger.error('Bestellungs-PDF: docxtpl-Rendering fehlgeschlagen: %s', exc)
        return None, None

    base_name = f'bestellung_{instructor.last_name}_{instructor.first_name}'.replace(' ', '_')
    title = f'Bestellung Praxistutor – {instructor.first_name} {instructor.last_name}'
    doc_id = upload_to_paperless(
        file_bytes=file_bytes,
        title=title,
        filename=f'{base_name}.docx',
        document_type='Bestellung Praxistutor',
    )
    if doc_id is None:
        logger.error('Bestellungs-PDF: Paperless-Upload für Instructor pk=%s fehlgeschlagen', instructor.pk)
        return None, None

    pdf_bytes = PaperlessService.download_pdf(doc_id)
    if not pdf_bytes:
        logger.error('Bestellungs-PDF: Download aus Paperless (doc_id=%s) fehlgeschlagen', doc_id)
        return None, None

    return pdf_bytes, f'{base_name}.pdf'


def notify_student_of_study_day_decision(request, study_day_request):
    """
    Benachrichtigt die Nachwuchskraft per E-Mail über die Entscheidung
    zu ihrem Lerntag-Antrag (Genehmigung oder Ablehnung).
    """
    from services.email import send_mail
    from services.models import NotificationTemplate

    student = study_day_request.student
    if not student.email_id:
        logger.info(
            'notify_student_of_study_day_decision: Nachwuchskraft %s hat keine E-Mail (Antrag pk=%s)',
            student, study_day_request.pk,
        )
        return

    key = 'study_day_approved' if study_day_request.status == 'approved' else 'study_day_rejected'
    portal_url = request.build_absolute_uri('/portal/lerntage/')
    anrede = f'Guten Tag {student.first_name} {student.last_name},'

    subject, body = NotificationTemplate.render(key, {
        'anrede':           anrede,
        'student_vorname':  student.first_name,
        'student_nachname': student.last_name,
        'datum':            study_day_request.date.strftime('%d.%m.%Y'),
        'ablehnungsgrund':  study_day_request.rejection_reason,
        'detail_url':       portal_url,
    })

    # Bei Genehmigung: Lerntag(e) als ganztägige iCal-Termineinladung anhängen.
    attachments = None
    if study_day_request.status == 'approved':
        from django.conf import settings
        from services.calendar import (
            build_event_ics,
            ics_attachment_tuple,
            stable_uid,
            daterange_end_exclusive,
            METHOD_REQUEST,
        )
        try:
            end_inclusive = study_day_request.date_end or study_day_request.date
            ics_bytes = build_event_ics(
                uid=stable_uid(study_day_request, 'lerntag'),
                summary=f'Lerntag: {student.first_name} {student.last_name}',
                start=study_day_request.date,
                end=daterange_end_exclusive(end_inclusive),
                description=(
                    f'Genehmigter Lern-/Studientag\n'
                    f'Nachwuchskraft: {student.first_name} {student.last_name}\n\n'
                    f'Übersicht: {portal_url}'
                ),
                organizer_email=settings.DEFAULT_FROM_EMAIL or None,
                attendee_emails=[student.email_id],
                sequence=study_day_request.notification_sequence,
                method=METHOD_REQUEST,
                url=portal_url,
            )
            attachments = [ics_attachment_tuple('lerntag.ics', ics_bytes, METHOD_REQUEST)]
        except Exception as exc:
            logger.warning('iCal-Anhang für Lerntag pk=%s konnte nicht erzeugt werden: %s', study_day_request.pk, exc)

    try:
        send_mail(
            subject=subject,
            body_text=body,
            recipient_list=[student.email_id],
            attachments=attachments,
        )
        logger.info(
            'Lerntag-Entscheidungsmail an %s gesendet (Antrag pk=%s, Status=%s)',
            student.email_id, study_day_request.pk, study_day_request.status,
        )
    except Exception as exc:
        logger.warning(
            'Lerntag-Entscheidungsmail an %s fehlgeschlagen: %s',
            student.email_id, exc,
        )

    # Interne Benachrichtigung im Portal
    if student.user:
        try:
            from services.models import create_notification
            if study_day_request.status == 'approved':
                create_notification(
                    student.user,
                    message=f'Lerntag genehmigt: {study_day_request.date.strftime("%d.%m.%Y")}',
                    link='/portal/lerntage/',
                    icon='bi-check-circle',
                    category='Lerntag',
                )
            else:
                create_notification(
                    student.user,
                    message=f'Lerntag abgelehnt: {study_day_request.date.strftime("%d.%m.%Y")}',
                    link='/portal/lerntage/',
                    icon='bi-x-circle',
                    category='Lerntag',
                )
        except Exception:
            pass


def notify_student_of_study_day_cancellation(request, study_day_request):
    """
    Benachrichtigt die Nachwuchskraft per E-Mail, wenn ein bereits
    genehmigter Lerntag durch das Ausbildungsreferat storniert wurde.
    """
    from services.email import send_mail
    from services.models import NotificationTemplate

    student = study_day_request.student
    if not student.email_id:
        return

    portal_url = request.build_absolute_uri('/portal/lerntage/')
    anrede = f'Guten Tag {student.first_name} {student.last_name},'

    subject, body = NotificationTemplate.render('study_day_cancelled', {
        'anrede':           anrede,
        'student_vorname':  student.first_name,
        'student_nachname': student.last_name,
        'datum':            study_day_request.date.strftime('%d.%m.%Y'),
        'detail_url':       portal_url,
    })

    # iCal-CANCEL mit identischer UID + erhöhter SEQUENCE entfernt den Termin
    # automatisch aus dem Outlook-Kalender der Nachwuchskraft.
    attachments = None
    from django.conf import settings
    from services.calendar import (
        build_event_ics,
        ics_attachment_tuple,
        stable_uid,
        daterange_end_exclusive,
        METHOD_CANCEL,
    )
    try:
        end_inclusive = study_day_request.date_end or study_day_request.date
        ics_bytes = build_event_ics(
            uid=stable_uid(study_day_request, 'lerntag'),
            summary=f'Lerntag: {student.first_name} {student.last_name}',
            start=study_day_request.date,
            end=daterange_end_exclusive(end_inclusive),
            description='Dieser Lerntag wurde storniert.',
            organizer_email=settings.DEFAULT_FROM_EMAIL or None,
            attendee_emails=[student.email_id],
            sequence=study_day_request.notification_sequence,
            method=METHOD_CANCEL,
            url=portal_url,
        )
        attachments = [ics_attachment_tuple('lerntag-stornierung.ics', ics_bytes, METHOD_CANCEL)]
    except Exception as exc:
        logger.warning('iCal-CANCEL für Lerntag pk=%s konnte nicht erzeugt werden: %s', study_day_request.pk, exc)

    try:
        send_mail(
            subject=subject,
            body_text=body,
            recipient_list=[student.email_id],
            attachments=attachments,
        )
        logger.info(
            'Lerntag-Stornierungsmail an %s gesendet (Antrag pk=%s)',
            student.email_id, study_day_request.pk,
        )
    except Exception as exc:
        logger.warning(
            'Lerntag-Stornierungsmail an %s fehlgeschlagen: %s',
            student.email_id, exc,
        )

    if student.user:
        try:
            from services.models import create_notification
            create_notification(
                student.user,
                message=f'Lerntag storniert: {study_day_request.date.strftime("%d.%m.%Y")}',
                link='/portal/lerntage/',
                icon='bi-dash-circle',
                category='Lerntag',
            )
        except Exception:
            pass


def notify_student_of_inventory_issuance(request, issuance):
    """Sendet der Nachwuchskraft eine Bestätigungsmail bei Ausgabe eines Gegenstands."""
    from services.email import send_mail
    from services.models import NotificationTemplate

    student = issuance.student
    if not student.email_id:
        logger.info(
            'notify_student_of_inventory_issuance: Nachwuchskraft %s hat keine E-Mail (Ausgabe pk=%s)',
            student, issuance.pk,
        )
        return

    subject, body = NotificationTemplate.render('inventory_issued', {
        'anrede':         f'Guten Tag {student.first_name} {student.last_name},',
        'gegenstand':     str(issuance.item),
        'seriennummer':   issuance.item.serial_number or '–',
        'kategorie':      issuance.item.category.name,
        'ausgabedatum':   issuance.issued_at.strftime('%d.%m.%Y %H:%M'),
        'ausgegeben_von': issuance.issued_by.get_full_name() or issuance.issued_by.username,
    })

    try:
        send_mail(subject=subject, body_text=body, recipient_list=[student.email_id])
        logger.info('Ausgabe-Bestätigungsmail an %s gesendet (Ausgabe pk=%s)', student.email_id, issuance.pk)
    except Exception as exc:
        logger.warning('Ausgabe-Bestätigungsmail an %s fehlgeschlagen: %s', student.email_id, exc)


def notify_student_of_inventory_return(request, issuance):
    """Sendet der Nachwuchskraft eine Bestätigungsmail bei Rücknahme eines Gegenstands."""
    from services.email import send_mail
    from services.models import NotificationTemplate

    student = issuance.student
    if not student.email_id:
        logger.info(
            'notify_student_of_inventory_return: Nachwuchskraft %s hat keine E-Mail (Ausgabe pk=%s)',
            student, issuance.pk,
        )
        return

    subject, body = NotificationTemplate.render('inventory_returned', {
        'anrede':          f'Guten Tag {student.first_name} {student.last_name},',
        'gegenstand':      str(issuance.item),
        'seriennummer':    issuance.item.serial_number or '–',
        'kategorie':       issuance.item.category.name,
        'rueckgabedatum':  issuance.returned_at.strftime('%d.%m.%Y %H:%M'),
        'bestaetigt_von':  (
            issuance.returned_acknowledged_by.get_full_name()
            or issuance.returned_acknowledged_by.username
        ),
    })

    try:
        send_mail(subject=subject, body_text=body, recipient_list=[student.email_id])
        logger.info('Rückgabe-Bestätigungsmail an %s gesendet (Ausgabe pk=%s)', student.email_id, issuance.pk)
    except Exception as exc:
        logger.warning('Rückgabe-Bestätigungsmail an %s fehlgeschlagen: %s', student.email_id, exc)


def notify_workspace_booking_confirmed(request, booking):
    """Bestätigt einer Nachwuchskraft die neue Raumbuchung mit iCal-Anhang (REQUEST).

    Funktionspostfach-/Funktionsmail-Logik wird hier nicht gebraucht – der
    Termin landet im persönlichen Outlook-Kalender der Nachwuchskraft.
    """
    from django.conf import settings
    from services.email import send_mail
    from services.calendar import (
        build_event_ics, ics_attachment_tuple, stable_uid,
        daterange_end_exclusive, METHOD_REQUEST,
    )

    student = booking.student
    if not student.email_id:
        logger.info(
            'notify_workspace_booking_confirmed: NK %s ohne E-Mail (Buchung pk=%s)',
            student, booking.pk,
        )
        return

    workspace = booking.workspace
    portal_url = request.build_absolute_uri(reverse_or_path('workspace:portal_my_bookings'))

    subject = f'Raumbuchung bestätigt: {workspace.name} am {booking.date.strftime("%d.%m.%Y")}'
    body = (
        f'Guten Tag {student.first_name} {student.last_name},\n\n'
        f'Ihre Buchung für „{workspace.name}" am '
        f'{booking.date.strftime("%d.%m.%Y")} wurde angelegt.\n\n'
        f'Standort: {workspace.location.name}\n'
        f'Typ: {workspace.workspace_type.name}\n'
    )
    if booking.purpose:
        body += f'Zweck: {booking.purpose}\n'
    body += f'\nÜbersicht Ihrer Buchungen: {portal_url}\n'

    attachments = None
    try:
        ics_bytes = build_event_ics(
            uid=stable_uid(booking, 'raumbuchung'),
            summary=f'Raumbuchung: {workspace.name}',
            start=booking.date,
            end=daterange_end_exclusive(booking.date),
            description=(
                f'Arbeitsplatz: {workspace.name}\n'
                f'Standort: {workspace.location.name}\n'
                + (f'Zweck: {booking.purpose}\n' if booking.purpose else '')
                + f'\nÜbersicht: {portal_url}'
            ),
            location=f'{workspace.location.name} – {workspace.name}',
            organizer_email=settings.DEFAULT_FROM_EMAIL or None,
            attendee_emails=[student.email_id],
            sequence=booking.notification_sequence,
            method=METHOD_REQUEST,
            url=portal_url,
        )
        attachments = [ics_attachment_tuple('raumbuchung.ics', ics_bytes, METHOD_REQUEST)]
    except Exception as exc:
        logger.warning('iCal für Raumbuchung pk=%s fehlgeschlagen: %s', booking.pk, exc)

    try:
        send_mail(subject=subject, body_text=body, recipient_list=[student.email_id], attachments=attachments)
        logger.info('Raumbuchungs-Bestätigung an %s gesendet (Buchung pk=%s)', student.email_id, booking.pk)
    except Exception as exc:
        logger.warning('Raumbuchungs-Bestätigung an %s fehlgeschlagen: %s', student.email_id, exc)


def notify_workspace_booking_cancelled(request, booking):
    """Storniert die Raumbuchung im Outlook-Kalender via iCal-CANCEL."""
    from django.conf import settings
    from services.email import send_mail
    from services.calendar import (
        build_event_ics, ics_attachment_tuple, stable_uid,
        daterange_end_exclusive, METHOD_CANCEL,
    )

    student = booking.student
    if not student.email_id:
        return

    workspace = booking.workspace
    portal_url = request.build_absolute_uri(reverse_or_path('workspace:portal_my_bookings'))

    subject = f'Raumbuchung storniert: {workspace.name} am {booking.date.strftime("%d.%m.%Y")}'
    body = (
        f'Guten Tag {student.first_name} {student.last_name},\n\n'
        f'Ihre Buchung für „{workspace.name}" am '
        f'{booking.date.strftime("%d.%m.%Y")} wurde storniert.\n\n'
        f'Übersicht Ihrer Buchungen: {portal_url}\n'
    )

    attachments = None
    try:
        ics_bytes = build_event_ics(
            uid=stable_uid(booking, 'raumbuchung'),
            summary=f'Raumbuchung: {workspace.name}',
            start=booking.date,
            end=daterange_end_exclusive(booking.date),
            description='Diese Raumbuchung wurde storniert.',
            location=f'{workspace.location.name} – {workspace.name}',
            organizer_email=settings.DEFAULT_FROM_EMAIL or None,
            attendee_emails=[student.email_id],
            sequence=booking.notification_sequence,
            method=METHOD_CANCEL,
            url=portal_url,
        )
        attachments = [ics_attachment_tuple('raumbuchung-stornierung.ics', ics_bytes, METHOD_CANCEL)]
    except Exception as exc:
        logger.warning('iCal-CANCEL für Raumbuchung pk=%s fehlgeschlagen: %s', booking.pk, exc)

    try:
        send_mail(subject=subject, body_text=body, recipient_list=[student.email_id], attachments=attachments)
        logger.info('Raumbuchungs-Stornierung an %s gesendet (Buchung pk=%s)', student.email_id, booking.pk)
    except Exception as exc:
        logger.warning('Raumbuchungs-Stornierung an %s fehlgeschlagen: %s', student.email_id, exc)


def reverse_or_path(viewname):
    """Lazy-import-freundlicher Wrapper um django.urls.reverse."""
    from django.urls import reverse
    return reverse(viewname)


def _get_coordinations_for_unit(unit):
    """Gibt alle Koordinationen zurück, in deren Verantwortungsbereich die Einheit liegt."""
    from instructor.models import TrainingCoordination

    ancestor_pks = [u.pk for u in unit.get_ancestors()] + [unit.pk]
    return TrainingCoordination.objects.filter(units__pk__in=ancestor_pks).prefetch_related('members').distinct()


def notify_chiefs_of_assignment(request, assignment, is_new: bool = True):
    """
    Sendet eine E-Mail an alle zuständigen Ausbildungskoordinationen,
    wenn ein Praktikumseinsatz angelegt oder geändert wird.

    Ist ein Funktionspostfach hinterlegt, geht eine Mail an das Postfach.
    Andernfalls wird jedes Mitglied der Koordination einzeln benachrichtigt.
    Der Link führt zur Detailseite der jeweiligen Koordination.
    """
    from services.email import send_mail
    from services.models import NotificationTemplate

    unit = assignment.unit
    student = assignment.student
    block = assignment.schedule_block

    coordinations = _get_coordinations_for_unit(unit)
    if not coordinations:
        return

    action = 'angelegt' if is_new else 'geändert'
    seen_addresses: set[str] = set()

    for coordination in coordinations:
        coordination_url = request.build_absolute_uri(f'/praxistutoren/koordination/{coordination.pk}/')

        if coordination.functional_email:
            recipients_with_greeting = [(coordination.functional_email, 'Guten Tag,', None)]
        else:
            recipients_with_greeting = [
                (chief.email, f'Guten Tag {chief.first_name} {chief.last_name},', chief.user if hasattr(chief, 'user') else None)
                for chief in coordination.members.all()
                if chief.email
            ]

        for recipient, anrede, django_user in recipients_with_greeting:
            if not recipient or recipient in seen_addresses:
                continue
            if not is_email_enabled(django_user, 'chief_assignment'):
                logger.info('chief_assignment übersprungen (deaktiviert): %s', recipient)
                continue
            seen_addresses.add(recipient)

            subject, body = NotificationTemplate.render('chief_assignment', {
                'anrede':           anrede,
                'action':           action,
                'student_vorname':  student.first_name,
                'student_nachname': student.last_name,
                'einheit':          unit.name,
                'von':              assignment.start_date.strftime('%d.%m.%Y'),
                'bis':              assignment.end_date.strftime('%d.%m.%Y'),
                'block':            block.name,
                'detail_url':       coordination_url,
            })

            try:
                send_mail(subject=subject, body_text=body, recipient_list=[recipient])
            except Exception as exc:
                logger.warning('Benachrichtigung an %s konnte nicht gesendet werden: %s', recipient, exc)


# ── Vorträge / Seminarblock ──────────────────────────────────────────────────

def _build_lecture_ics(lecture, *, method, sequence=None):
    """Baut ein iCal-Attachment-Tupel für einen Vortrag."""
    from django.conf import settings
    from services.calendar import (
        build_event_ics,
        ics_attachment_tuple,
        stable_uid,
        METHOD_REQUEST,
        METHOD_CANCEL,
    )
    if sequence is None:
        sequence = lecture.notification_sequence
    description_parts = []
    if lecture.description:
        description_parts.append(lecture.description)
    description_parts.append(f'Vortragender: {lecture.speaker_name}')
    description_parts.append(f'Seminar: {lecture.schedule_block.name}')
    ics_bytes = build_event_ics(
        uid=stable_uid(lecture, 'vortrag'),
        summary=f'Vortrag: {lecture.topic}',
        start=lecture.start_datetime,
        end=lecture.end_datetime,
        description='\n'.join(description_parts),
        location=lecture.location or '',
        organizer_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None,
        attendee_emails=[lecture.speaker_email],
        sequence=sequence,
        method=method,
    )
    filename = 'vortrag-storno.ics' if method == METHOD_CANCEL else 'vortrag.ics'
    return ics_attachment_tuple(filename, ics_bytes, method)


def _lecture_links(request, lecture):
    confirm_url = request.build_absolute_uri(f'/vortrag/{lecture.confirmation_token}/bestaetigen/')
    decline_url = request.build_absolute_uri(f'/vortrag/{lecture.confirmation_token}/ablehnen/')
    return confirm_url, decline_url


def notify_lecture_request(request, lecture):
    """Sendet die initiale Bestätigungsanfrage an den Vortragenden (mit .ics-REQUEST)."""
    from django.utils import timezone
    from services.email import send_mail
    from services.models import NotificationTemplate
    from services.calendar import METHOD_REQUEST

    confirm_url, decline_url = _lecture_links(request, lecture)
    subject, body = NotificationTemplate.render('lecture_request', {
        'anrede':      f'Guten Tag {lecture.speaker_name},',
        'thema':       lecture.topic,
        'inhalt':      lecture.description,
        'ort':         lecture.location,
        'datum':       lecture.start_datetime.strftime('%d.%m.%Y'),
        'beginn':      lecture.start_datetime.strftime('%H:%M'),
        'ende':        lecture.end_datetime.strftime('%H:%M'),
        'seminar':     lecture.schedule_block.name,
        'confirm_url': confirm_url,
        'decline_url': decline_url,
    })
    attachments = None
    try:
        attachments = [_build_lecture_ics(lecture, method=METHOD_REQUEST)]
    except Exception as exc:
        logger.warning('iCal-Anhang für Vortrag pk=%s konnte nicht erzeugt werden: %s', lecture.pk, exc)
    try:
        send_mail(subject=subject, body_text=body,
                  recipient_list=[lecture.speaker_email],
                  attachments=attachments)
        lecture.sent_at = timezone.now()
        lecture.save(update_fields=['sent_at'])
    except Exception as exc:
        logger.error('Vortragsanfrage an %s fehlgeschlagen: %s', lecture.speaker_email, exc)


def notify_lecture_reminder(lecture):
    """Sendet eine Erinnerung an den Vortragenden, wenn nach 10 Tagen keine Antwort kam.
    Diese Funktion läuft im Celery-Task – kein request verfügbar, daher absolute URLs
    aus settings."""
    from django.conf import settings
    from django.utils import timezone
    from services.email import send_mail
    from services.models import NotificationTemplate

    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    confirm_url = f'{base}/vortrag/{lecture.confirmation_token}/bestaetigen/'
    decline_url = f'{base}/vortrag/{lecture.confirmation_token}/ablehnen/'
    subject, body = NotificationTemplate.render('lecture_reminder', {
        'anrede':      f'Guten Tag {lecture.speaker_name},',
        'thema':       lecture.topic,
        'datum':       lecture.start_datetime.strftime('%d.%m.%Y'),
        'beginn':      lecture.start_datetime.strftime('%H:%M'),
        'ende':        lecture.end_datetime.strftime('%H:%M'),
        'confirm_url': confirm_url,
        'decline_url': decline_url,
    })
    try:
        send_mail(subject=subject, body_text=body, recipient_list=[lecture.speaker_email])
        lecture.reminder_sent_at = timezone.now()
        lecture.save(update_fields=['reminder_sent_at'])
    except Exception as exc:
        logger.error('Vortrags-Erinnerung an %s fehlgeschlagen: %s', lecture.speaker_email, exc)


def notify_lecture_update(request, lecture):
    """Sendet ein iCal-UPDATE an den Vortragenden, wenn sich Details nach Bestätigung ändern."""
    from services.email import send_mail
    from services.models import NotificationTemplate
    from services.calendar import METHOD_REQUEST

    subject, body = NotificationTemplate.render('lecture_update', {
        'anrede': f'Guten Tag {lecture.speaker_name},',
        'thema':  lecture.topic,
        'datum':  lecture.start_datetime.strftime('%d.%m.%Y'),
        'beginn': lecture.start_datetime.strftime('%H:%M'),
        'ende':   lecture.end_datetime.strftime('%H:%M'),
        'ort':    lecture.location,
    })
    attachments = None
    try:
        attachments = [_build_lecture_ics(lecture, method=METHOD_REQUEST)]
    except Exception as exc:
        logger.warning('iCal-Update für Vortrag pk=%s konnte nicht erzeugt werden: %s', lecture.pk, exc)
    try:
        send_mail(subject=subject, body_text=body,
                  recipient_list=[lecture.speaker_email],
                  attachments=attachments)
    except Exception as exc:
        logger.error('Vortrags-Update an %s fehlgeschlagen: %s', lecture.speaker_email, exc)


def notify_lecture_cancelled(request, lecture):
    """Sendet eine Storno-Mail mit iCal-CANCEL an den Vortragenden."""
    from services.email import send_mail
    from services.models import NotificationTemplate
    from services.calendar import METHOD_CANCEL

    subject, body = NotificationTemplate.render('lecture_cancelled', {
        'anrede': f'Guten Tag {lecture.speaker_name},',
        'thema':  lecture.topic,
        'datum':  lecture.start_datetime.strftime('%d.%m.%Y'),
        'beginn': lecture.start_datetime.strftime('%H:%M'),
    })
    attachments = None
    try:
        attachments = [_build_lecture_ics(
            lecture,
            method=METHOD_CANCEL,
            sequence=lecture.notification_sequence + 1,
        )]
    except Exception as exc:
        logger.warning('iCal-Storno für Vortrag pk=%s konnte nicht erzeugt werden: %s', lecture.pk, exc)
    try:
        send_mail(subject=subject, body_text=body,
                  recipient_list=[lecture.speaker_email],
                  attachments=attachments)
    except Exception as exc:
        logger.error('Vortrags-Storno an %s fehlgeschlagen: %s', lecture.speaker_email, exc)


def notify_lecture_decision(lecture):
    """Benachrichtigt den Ersteller über die Entscheidung des Vortragenden – per
    E-Mail und als Portal-Notification."""
    from django.conf import settings
    from services.email import send_mail
    from services.models import NotificationTemplate, create_notification

    creator = lecture.created_by
    if not creator:
        return

    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    block = lecture.schedule_block
    detail_url = f'{base}/kurs/{block.course_id}/ablaufplan/{block.public_id}/seminar/'

    is_confirmed = lecture.status == 'confirmed'
    key = 'lecture_confirmed_creator' if is_confirmed else 'lecture_declined_creator'

    if is_confirmed:
        message = f'Vortrag bestätigt: {lecture.speaker_name} – {lecture.topic}'
        icon = 'bi-check-circle'
    else:
        message = f'Vortrag abgelehnt: {lecture.speaker_name} – {lecture.topic}'
        icon = 'bi-x-circle'

    try:
        create_notification(
            creator,
            message=message,
            link=f'/kurs/{block.course_id}/ablaufplan/{block.public_id}/seminar/',
            icon=icon,
            category='Vortrag',
        )
    except Exception:
        logger.exception('Portal-Notification für Vortragsentscheidung pk=%s fehlgeschlagen', lecture.pk)

    if not creator.email or not is_email_enabled(creator, key):
        return
    subject, body = NotificationTemplate.render(key, {
        'vorname':         creator.first_name,
        'nachname':        creator.last_name,
        'vortragender':    lecture.speaker_name,
        'thema':           lecture.topic,
        'datum':           lecture.start_datetime.strftime('%d.%m.%Y'),
        'beginn':          lecture.start_datetime.strftime('%H:%M'),
        'ablehnungsgrund': lecture.decline_reason,
        'detail_url':      detail_url,
    })
    try:
        send_mail(subject=subject, body_text=body, recipient_list=[creator.email])
    except Exception as exc:
        logger.warning('Vortrags-Entscheidungs-Mail an %s fehlgeschlagen: %s', creator.email, exc)
