"""Datenmodell der Workflow-Engine.

Eine `WorkflowDefinition` beschreibt eine Workflow-Vorlage (z.B. „Urlaubsantrag").
Sie besteht aus einer geordneten Liste von `WorkflowStep`-Stufen. Pro Antrag
wird eine `WorkflowInstance` angelegt, die genau ein fachliches Zielobjekt
(VacationRequest, StudyDayRequest, …) referenziert. Jede Aktion (Approve,
Reject, Reminder, Eskalation) erzeugt einen `WorkflowTransition`-Eintrag und
sorgt so für einen vollständigen Audit-Trail.
"""
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


# ── Workflow-Status ─────────────────────────────────────────────────────────
INSTANCE_STATUS_IN_PROGRESS = 'in_progress'
INSTANCE_STATUS_APPROVED    = 'approved'
INSTANCE_STATUS_REJECTED    = 'rejected'
INSTANCE_STATUS_CANCELLED   = 'cancelled'

INSTANCE_STATUS_CHOICES = [
    (INSTANCE_STATUS_IN_PROGRESS, 'Läuft'),
    (INSTANCE_STATUS_APPROVED,    'Genehmigt'),
    (INSTANCE_STATUS_REJECTED,    'Abgelehnt'),
    (INSTANCE_STATUS_CANCELLED,   'Storniert'),
]

# ── Approver-Typen ──────────────────────────────────────────────────────────
APPROVER_ROLE           = 'role'
APPROVER_USER           = 'user'
APPROVER_DYNAMIC        = 'dynamic'
APPROVER_EXTERNAL_TOKEN = 'external_token'
APPROVER_INFO           = 'info'

APPROVER_TYPE_CHOICES = [
    (APPROVER_ROLE,           'Rolle'),
    (APPROVER_USER,           'Bestimmter Benutzer'),
    (APPROVER_DYNAMIC,        'Dynamisch (kontextabhängig)'),
    (APPROVER_EXTERNAL_TOKEN, 'Externer Token-Approver'),
    (APPROVER_INFO,           'Info-Step (nicht blockierend)'),
]

# ── Timeout-Verhalten ───────────────────────────────────────────────────────
TIMEOUT_REMIND         = 'remind'
TIMEOUT_ESCALATE_NEXT  = 'escalate_next'
TIMEOUT_ESCALATE_TO    = 'escalate_to'
TIMEOUT_AUTO_APPROVE   = 'auto_approve'
TIMEOUT_AUTO_REJECT    = 'auto_reject'

TIMEOUT_CHOICES = [
    (TIMEOUT_REMIND,        'Nur Erinnerung'),
    (TIMEOUT_ESCALATE_NEXT, 'Auf nächste Stufe eskalieren'),
    (TIMEOUT_ESCALATE_TO,   'An bestimmten Approver eskalieren'),
    (TIMEOUT_AUTO_APPROVE,  'Automatisch genehmigen'),
    (TIMEOUT_AUTO_REJECT,   'Automatisch ablehnen'),
]

# ── Reject-Verhalten pro Workflow ───────────────────────────────────────────
REJECT_BEHAVIOR_FINAL        = 'final'
REJECT_BEHAVIOR_TO_FIRST     = 'to_first'
REJECT_BEHAVIOR_TO_INITIATOR = 'to_initiator'

REJECT_BEHAVIOR_CHOICES = [
    (REJECT_BEHAVIOR_FINAL,        'Endgültig abgelehnt'),
    (REJECT_BEHAVIOR_TO_FIRST,     'Zurück auf erste Stufe (History bleibt)'),
    (REJECT_BEHAVIOR_TO_INITIATOR, 'Zurück an Antragsteller zur Überarbeitung'),
]

# ── Transitions-Aktionen ────────────────────────────────────────────────────
ACTION_SUBMIT       = 'submit'
ACTION_APPROVE      = 'approve'
ACTION_REJECT       = 'reject'
ACTION_CANCEL       = 'cancel'
ACTION_REMIND       = 'remind'
ACTION_ESCALATE     = 'escalate'
ACTION_AUTO_APPROVE = 'auto_approve'
ACTION_AUTO_REJECT  = 'auto_reject'
ACTION_ACKNOWLEDGE  = 'acknowledge'
ACTION_RESUBMIT     = 'resubmit'

ACTION_CHOICES = [
    (ACTION_SUBMIT,       'Eingereicht'),
    (ACTION_APPROVE,      'Genehmigt'),
    (ACTION_REJECT,       'Abgelehnt'),
    (ACTION_CANCEL,       'Storniert'),
    (ACTION_REMIND,       'Erinnerung versandt'),
    (ACTION_ESCALATE,     'Eskaliert'),
    (ACTION_AUTO_APPROVE, 'Automatisch genehmigt'),
    (ACTION_AUTO_REJECT,  'Automatisch abgelehnt'),
    (ACTION_ACKNOWLEDGE,  'Zur Kenntnis genommen'),
    (ACTION_RESUBMIT,     'Erneut eingereicht'),
]


class WorkflowDefinition(models.Model):
    """Vorlage für einen Workflow-Typ (z.B. 'vacation_request')."""

    code = models.SlugField(
        max_length=64, unique=True,
        verbose_name='Code',
        help_text='Eindeutiger technischer Bezeichner, z.B. „vacation_request". '
                  'Wird vom Modul-Code referenziert und darf nach Anlage nicht '
                  'mehr geändert werden.',
    )
    name = models.CharField(
        max_length=200,
        verbose_name='Bezeichnung',
        help_text='Sprechender Name, der im Admin und in Benachrichtigungen erscheint.',
    )
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv',
        help_text='Inaktive Workflows starten keine neuen Instanzen. Laufende '
                  'Instanzen werden nach altem Stand abgearbeitet.',
    )
    pre_condition = models.CharField(
        max_length=500, blank=True,
        verbose_name='Vorbedingung',
        help_text='Optionaler Ausdruck. Wenn gesetzt und falsch beim Start, '
                  'wird die Instanz sofort als genehmigt markiert (Approval '
                  'übersprungen). Beispiele: '
                  '„initiator.announcement_requires_approval", '
                  '„target.duration > 14".',
    )
    reject_behavior = models.CharField(
        max_length=20,
        choices=REJECT_BEHAVIOR_CHOICES,
        default=REJECT_BEHAVIOR_FINAL,
        verbose_name='Verhalten bei Ablehnung',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Workflow-Definition'
        verbose_name_plural = 'Workflow-Definitionen'
        ordering            = ['name']

    def __str__(self):
        return self.name

    def active_steps(self):
        return self.steps.order_by('order')


class WorkflowStep(models.Model):
    """Eine Stufe in einem Workflow."""

    workflow = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    order = models.PositiveIntegerField(
        verbose_name='Reihenfolge',
        help_text='Niedrigste Zahl = erste Stufe.',
    )
    name = models.CharField(
        max_length=200,
        verbose_name='Stufen-Name',
        help_text='z.B. „Prüfung durch Ausbildungsreferat".',
    )
    approver_type = models.CharField(
        max_length=20,
        choices=APPROVER_TYPE_CHOICES,
        verbose_name='Approver-Typ',
    )
    approver_value = models.CharField(
        max_length=200, blank=True,
        verbose_name='Approver-Wert',
        help_text='Kontextabhängig: Rollen-Name (z.B. „training_office"), '
                  'User-PK, Resolver-Code für „dynamisch", '
                  'oder leer für „info".',
    )
    deadline_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Frist in Tagen',
        help_text='Nach dieser Anzahl Tagen wird das Timeout-Verhalten ausgelöst. '
                  'Leer = keine Frist.',
    )
    on_timeout = models.CharField(
        max_length=20,
        choices=TIMEOUT_CHOICES,
        default=TIMEOUT_REMIND,
        verbose_name='Bei Fristablauf',
    )
    escalate_to_value = models.CharField(
        max_length=200, blank=True,
        verbose_name='Eskalations-Ziel',
        help_text='Nur bei „escalate_to": Rollen-Code des Eskalations-Approvers '
                  '(z.B. „training_director").',
    )
    skip_condition = models.CharField(
        max_length=500, blank=True,
        verbose_name='Übersprungs-Bedingung',
        help_text='Wenn gesetzt und wahr, wird diese Stufe automatisch übersprungen.',
    )

    class Meta:
        verbose_name        = 'Workflow-Stufe'
        verbose_name_plural = 'Workflow-Stufen'
        ordering            = ['workflow', 'order']
        unique_together     = [('workflow', 'order')]

    def __str__(self):
        return f'{self.workflow.name} · Stufe {self.order}: {self.name}'


class WorkflowInstance(models.Model):
    """Eine konkrete Workflow-Instanz für ein Zielobjekt."""

    public_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True,
        verbose_name='Öffentliche ID',
    )
    definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name='instances',
        verbose_name='Workflow-Definition',
    )

    target_ct = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        verbose_name='Ziel-Modell',
    )
    target_id = models.PositiveIntegerField(verbose_name='Ziel-ID')
    target = GenericForeignKey('target_ct', 'target_id')

    current_step = models.ForeignKey(
        WorkflowStep, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='current_instances',
        verbose_name='Aktuelle Stufe',
        help_text='Null, wenn Workflow beendet ist.',
    )
    status = models.CharField(
        max_length=20,
        choices=INSTANCE_STATUS_CHOICES,
        default=INSTANCE_STATUS_IN_PROGRESS,
        verbose_name='Status',
    )

    initiator = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='workflow_instances_initiated',
        verbose_name='Antragsteller:in',
    )
    started_at  = models.DateTimeField(auto_now_add=True, verbose_name='Gestartet am')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Beendet am')
    current_step_started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Aktuelle Stufe seit',
        help_text='Wird bei jedem Stufenwechsel aktualisiert. Basis für Frist-Berechnung.',
    )

    revision = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Revision',
        help_text='Zählt hoch, wenn ein abgelehnter Antrag erneut eingereicht wird.',
    )

    class Meta:
        verbose_name        = 'Workflow-Instanz'
        verbose_name_plural = 'Workflow-Instanzen'
        ordering            = ['-started_at']
        indexes = [
            models.Index(fields=['target_ct', 'target_id']),
            models.Index(fields=['status', 'current_step']),
        ]

    def __str__(self):
        return f'{self.definition.name} #{self.pk} ({self.get_status_display()})'

    @property
    def is_active(self):
        return self.status == INSTANCE_STATUS_IN_PROGRESS

    @property
    def is_finished(self):
        return self.status in (INSTANCE_STATUS_APPROVED, INSTANCE_STATUS_REJECTED,
                               INSTANCE_STATUS_CANCELLED)


class WorkflowTransition(models.Model):
    """Audit-Eintrag für einen Status-Übergang."""

    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE,
        related_name='transitions',
    )
    step = models.ForeignKey(
        WorkflowStep, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transitions',
        verbose_name='Stufe',
    )
    revision = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Revision',
    )
    actor = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='workflow_actions',
        verbose_name='Aktor:in',
    )
    actor_name = models.CharField(
        max_length=200, blank=True,
        verbose_name='Aktor-Name',
        help_text='Klartext für externe (Token-)Approver oder Systemaktionen.',
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='Aktion',
    )
    comment = models.TextField(blank=True, verbose_name='Kommentar')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Zeitpunkt')

    class Meta:
        verbose_name        = 'Workflow-Transition'
        verbose_name_plural = 'Workflow-Transitions'
        ordering            = ['instance', 'timestamp']

    def __str__(self):
        return f'{self.instance} · {self.get_action_display()} ({self.timestamp:%d.%m.%Y %H:%M})'


class WorkflowReminder(models.Model):
    """Verfolgt gesendete Erinnerungen — verhindert mehrfache Reminder."""

    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE,
        related_name='reminders',
    )
    step = models.ForeignKey(
        WorkflowStep, on_delete=models.CASCADE,
        related_name='reminders',
    )
    revision = models.PositiveSmallIntegerField(default=1)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Workflow-Erinnerung'
        verbose_name_plural = 'Workflow-Erinnerungen'
        ordering            = ['-sent_at']
        unique_together     = [('instance', 'step', 'revision')]
