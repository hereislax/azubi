# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Defines which models and fields are tracked by the audit log.

Each entry maps a (app_label, model_name) tuple to a list of field names to watch.
Fields listed here must exist on the model. FK fields are serialized via __str__().
Choice fields are serialized as their human-readable label.
"""

TRACKED_FIELDS = {
    # ── Nachwuchskräfte ───────────────────────────────────────────────────────
    ('student', 'student'): [
        'first_name', 'last_name', 'gender',
        'date_of_birth', 'place_of_birth',
        'phone_number', 'email_private', 'email_id',
        'course', 'employment', 'status',
        'anonymized_at',
    ],
    ('student', 'grade'): [
        'student', 'grade_type', 'value', 'date', 'notes',
    ],

    # ── Kurse & Ablaufpläne ───────────────────────────────────────────────────
    ('course', 'course'): [
        'title', 'start_date', 'end_date', 'job_profile',
    ],
    ('course', 'scheduleblock'): [
        'course', 'name', 'location', 'start_date', 'end_date', 'block_type',
    ],
    ('course', 'internshipassignment'): [
        'student', 'unit', 'start_date', 'end_date',
        'instructor', 'location', 'status', 'rejection_reason',
    ],

    # ── Ausbildungsnachweise ──────────────────────────────────────────────────
    ('proofoftraining', 'trainingrecord'): [
        'status', 'rejection_reason',
    ],

    # ── Wohnheim-Belegungen ───────────────────────────────────────────────────
    ('dormitory', 'roomassignment'): [
        'student', 'room', 'start_date', 'end_date', 'notes',
    ],

    # ── Stationsbeurteilungen ─────────────────────────────────────────────────
    # Token & reminder_count/last_reminder_at bewusst nicht getrackt:
    # Token enthält Zugangs-Geheimnis, Reminder erzeugen sonst Log-Rauschen.
    ('assessment', 'assessment'): [
        'status', 'submitted_at',
        'confirmed_by', 'confirmed_at',
        'assessor_name', 'assessor_email',
        'token_sent_at',
        'escalated_at', 'escalated_to',
    ],
    ('assessment', 'assessmentrating'): [
        'assessment', 'criterion', 'value', 'comment',
    ],
    ('assessment', 'assessmenttemplate'): [
        'job_profile', 'name', 'rating_scale',
        'instructions_assessor', 'instructions_self', 'active',
    ],
    ('assessment', 'assessmentcriterion'): [
        'job_profile', 'name', 'category', 'order', 'help_text',
    ],

    # ── Pflichtschulungen ─────────────────────────────────────────────────────
    ('mandatorytraining', 'trainingtype'): [
        'name', 'description', 'recurrence',
        'validity_months', 'fixed_deadline_month', 'fixed_deadline_day',
        'fixed_recurrence_years', 'reminder_days_before',
        'is_mandatory', 'applies_to_all_students', 'active',
    ],
    ('mandatorytraining', 'trainingcompletion'): [
        'student', 'training_type', 'completed_on', 'expires_on',
        'certificate_paperless_id', 'notes',
    ],

    # ── Praxistutoren & Ausbildungskoordinationen ─────────────────────────────
    ('instructor', 'instructor'): [
        'salutation', 'first_name', 'last_name', 'email',
        'unit', 'location', 'status',
    ],
    ('instructor', 'chiefinstructor'): [
        'salutation', 'first_name', 'last_name', 'email',
        'coordination', 'user',
    ],
    ('instructor', 'trainingcoordination'): [
        'name', 'functional_email',
    ],

    # ── Inventarverwaltung ────────────────────────────────────────────────────
    ('inventory', 'inventoryitem'): [
        'category', 'name', 'serial_number', 'status', 'location', 'notes',
    ],
    ('inventory', 'inventoryissuance'): [
        'item', 'student', 'issued_by', 'issued_at',
        'returned_at', 'returned_acknowledged_by', 'notes',
    ],
    ('inventory', 'inventorycategory'): [
        'name', 'receipt_template',
    ],

    # ── Abwesenheiten (Urlaub & Krankmeldungen) ───────────────────────────────
    ('absence', 'vacationrequest'): [
        'student', 'start_date', 'end_date', 'is_cancellation',
        'status', 'approved_by', 'approved_at', 'rejection_reason',
        'cancelled_by', 'cancelled_at', 'manual_working_days',
    ],
    ('absence', 'sickleave'): [
        'student', 'start_date', 'end_date', 'sick_type', 'notes',
        'closed_by', 'closed_at',
    ],
    ('absence', 'absencesettings'): [
        'vacation_office_email', 'holiday_state',
    ],

    # ── SSO-Verknüpfungen (allauth-SocialAccount) ─────────────────────────────
    # Nur Identifizierungsfelder, NICHT last_login (sonst flutet jeder Login
    # den Audit-Log).
    ('socialaccount', 'socialaccount'): [
        'user', 'provider', 'uid',
    ],

    # ── 2FA-Geräte (django-otp) ──────────────────────────────────────────────
    # Nur Aktivierung/Deaktivierung, NICHT last_t/drift (würde jeden Login loggen).
    ('otp_totp',   'totpdevice'):   ['user', 'name', 'confirmed'],
    ('otp_static', 'staticdevice'): ['user', 'name', 'confirmed'],
}


def _student_id_from_instance(instance):
    """
    Extract a student_id from a model instance for easy per-student filtering.
    Returns a string PK or None.
    """
    # Direkter Student-FK
    student = getattr(instance, 'student', None)
    if student is not None:
        return str(student.pk) if hasattr(student, 'pk') else str(student)
    # Indirekt über assignment.student (Assessment, evtl. weitere FK-Modelle)
    assignment = getattr(instance, 'assignment', None)
    if assignment is not None:
        sub_student = getattr(assignment, 'student', None)
        if sub_student is not None:
            return str(sub_student.pk) if hasattr(sub_student, 'pk') else str(sub_student)
    # Indirekt über assessment.assignment.student (AssessmentRating)
    assessment = getattr(instance, 'assessment', None)
    if assessment is not None:
        assignment = getattr(assessment, 'assignment', None)
        if assignment is not None:
            sub_student = getattr(assignment, 'student', None)
            if sub_student is not None:
                return str(sub_student.pk) if hasattr(sub_student, 'pk') else str(sub_student)
    # Die Instanz selbst ist eine Nachwuchskraft
    from django.apps import apps
    try:
        Student = apps.get_model('student', 'Student')
        if isinstance(instance, Student):
            return str(instance.pk)
    except LookupError:
        pass
    return None
