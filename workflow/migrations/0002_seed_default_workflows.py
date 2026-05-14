"""Daten-Migration: legt Default-Workflows an.

Hier wird der erste Workflow (`study_day_request`) als Standard-Definition
angelegt — mit einer Stufe „Ausbildungsreferat", Frist 5 Tage,
Timeout → Eskalation an Leitung. Diese Definition kann vom Admin später
unter Einstellungen › Genehmigungs-Workflows angepasst werden.
"""
from django.db import migrations


def seed_default_workflows(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    # ── study_day_request ──────────────────────────────────────────────────
    wd, created = WorkflowDefinition.objects.get_or_create(
        code='study_day_request',
        defaults={
            'name':            'Lerntag-Antrag',
            'description':     'Antrag einer Nachwuchskraft auf einen Lerntag.',
            'is_active':       True,
            'reject_behavior': 'final',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Prüfung durch Ausbildungsreferat',
            approver_type='role',
            approver_value='training_office',
            deadline_days=5,
            on_timeout='escalate_to',
            escalate_to_value='training_director',
        )

    # ── announcement_publish ───────────────────────────────────────────────
    wd2, created2 = WorkflowDefinition.objects.get_or_create(
        code='announcement_publish',
        defaults={
            'name':            'Ankündigung freigeben',
            'description':     'Ankündigungen von Nicht-Sachbearbeiter:innen werden vor der '
                               'Veröffentlichung von der Ausbildungsleitung freigegeben.',
            'is_active':       True,
            'reject_behavior': 'to_initiator',
            # Pre-Condition: nur wenn der Verfasser kein „Sachbearbeiter" ist
            # (UserProfile.announcement_requires_approval = True)
            'pre_condition':   'initiator.profile.announcement_requires_approval',
        },
    )
    if created2:
        WorkflowStep.objects.create(
            workflow=wd2,
            order=1,
            name='Freigabe durch Ausbildungsleitung',
            approver_type='role',
            approver_value='training_director',
            deadline_days=3,
            on_timeout='remind',
        )


def remove_default_workflows(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(
        code__in=['study_day_request', 'announcement_publish']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_workflows, reverse_code=remove_default_workflows),
    ]
