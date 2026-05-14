"""Daten-Migration: legt den Workflow für Praktikumseinsätze an.

Eine Stufe:
- Genehmigung durch die zuständige Ausbildungskoordination (Frist 5 Tage,
  Eskalation an die Ausbildungsleitung).

Reject-Verhalten: ``final`` — abgelehnte Einsätze werden vom Referat neu
angelegt; eine Wiedereinreichung erfolgt nicht über denselben Workflow-Datensatz.
"""
from django.db import migrations


def seed_internship_assignment_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    wd, created = WorkflowDefinition.objects.get_or_create(
        code='internship_assignment',
        defaults={
            'name':            'Praktikumseinsatz',
            'description':     'Genehmigung eines vom Ausbildungsreferat geplanten '
                               'Praktikumseinsatzes durch die zuständige '
                               'Ausbildungskoordination.',
            'is_active':       True,
            'reject_behavior': 'final',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Annahme durch Ausbildungskoordination',
            approver_type='role',
            approver_value='training_coordinator',
            deadline_days=5,
            on_timeout='escalate_to',
            escalate_to_value='training_director',
        )


def remove_internship_assignment_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(code='internship_assignment').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0005_seed_assessment_workflow'),
    ]

    operations = [
        migrations.RunPython(seed_internship_assignment_workflow,
                              reverse_code=remove_internship_assignment_workflow),
    ]
