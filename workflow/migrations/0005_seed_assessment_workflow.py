"""Daten-Migration: legt den Workflow für Stationsbeurteilungen an.

Drei Stufen:
- Stufe 1: Praxistutor reicht ein (Approver-Typ ``external_token``, kein Login).
  Frist 21 Tage; bei Überschreitung Eskalation an die Ausbildungskoordination.
- Stufe 2: Ausbildungskoordination zeichnet zur Kenntnis ab (Approver-Typ ``info``).
  Frist 7 Tage; bei Überschreitung wird die Stufe übersprungen.
- Stufe 3: Ausbildungsreferat bestätigt (Approver-Typ ``role`` → ``training_office``).
  Frist 7 Tage; bei Überschreitung Erinnerung.

Reject-Verhalten: ``final`` — eine abgebrochene Beurteilung muss neu gestartet werden.
"""
from django.db import migrations


def seed_assessment_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    wd, created = WorkflowDefinition.objects.get_or_create(
        code='assessment_confirm',
        defaults={
            'name':            'Stationsbeurteilung',
            'description':     'Beurteilung eines Praxiseinsatzes durch den Praxistutoren, '
                               'Kenntnisnahme durch die Ausbildungskoordination und '
                               'Bestätigung durch das Ausbildungsreferat.',
            'is_active':       True,
            'reject_behavior': 'final',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Einreichung durch Praxistutor',
            approver_type='external_token',
            approver_value='assessment_token',
            deadline_days=21,
            on_timeout='escalate_to',
            escalate_to_value='training_coordinator',
        )
        WorkflowStep.objects.create(
            workflow=wd,
            order=2,
            name='Kenntnisnahme durch Ausbildungskoordination',
            approver_type='info',
            approver_value='training_coordinator',
            deadline_days=7,
            on_timeout='escalate_next',
        )
        WorkflowStep.objects.create(
            workflow=wd,
            order=3,
            name='Bestätigung durch Ausbildungsreferat',
            approver_type='role',
            approver_value='training_office',
            deadline_days=7,
            on_timeout='remind',
        )


def remove_assessment_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(code='assessment_confirm').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0004_seed_training_record_workflow'),
    ]

    operations = [
        migrations.RunPython(seed_assessment_workflow,
                              reverse_code=remove_assessment_workflow),
    ]
