"""Daten-Migration: Workflow für Änderungsanträge an Praktikumseinsätzen.

Eine Stufe:
- Genehmigung durch die Ausbildungsleitung (Frist 3 Tage, Erinnerung bei
  Überschreitung).

Conditional-Routing: ``pre_condition = 'target.requires_approval'``.
Damit überspringt z.B. der Änderungstyp „Praxistutor wechseln" den Workflow
automatisch und wird vom Mirror als „auto_approved" markiert.

Administrator:innen können die Bedingung später erweitern, etwa um eine
Zeitabstand-Komponente:
    target.requires_approval and target.is_short_notice
→ Genehmigung nur bei kurzfristigen Änderungen (< 14 Tage vor Einsatzbeginn).

Reject-Verhalten: ``final``.
"""
from django.db import migrations


def seed_change_request_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    wd, created = WorkflowDefinition.objects.get_or_create(
        code='assignment_change_request',
        defaults={
            'name':            'Änderungsantrag (Praxiseinsatz)',
            'description':     'Änderungen an Praktikumseinsätzen (Splitten, Verschieben, '
                               'Stationswechsel, Standortwechsel, Stornieren) werden von der '
                               'Ausbildungsleitung freigegeben. Änderungen, deren Typ keine '
                               'Genehmigung erfordert (z. B. Praxistutor-Wechsel), werden '
                               'durch die Pre-Condition automatisch genehmigt.',
            'is_active':       True,
            'reject_behavior': 'final',
            'pre_condition':   'target.requires_approval',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Freigabe durch Ausbildungsleitung',
            approver_type='role',
            approver_value='training_director',
            deadline_days=3,
            on_timeout='remind',
        )


def remove_change_request_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(code='assignment_change_request').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0006_seed_internship_assignment_workflow'),
    ]

    operations = [
        migrations.RunPython(seed_change_request_workflow,
                              reverse_code=remove_change_request_workflow),
    ]
