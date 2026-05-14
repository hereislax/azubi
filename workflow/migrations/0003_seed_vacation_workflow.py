"""Daten-Migration: legt den Workflow für Urlaubsanträge an.

Zwei Stufen:
- Stufe 1: Genehmigung durch Ausbildungsreferat (Frist 5 Tage, Eskalation an Leitung)
- Stufe 2: Bearbeitung durch Urlaubsstelle (Resturlaubs-Eintragung)

Reject-Verhalten: ``final`` — abgelehnte Anträge müssen erneut gestellt werden.
"""
from django.db import migrations


def seed_vacation_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    wd, created = WorkflowDefinition.objects.get_or_create(
        code='vacation_request',
        defaults={
            'name':            'Urlaubsantrag',
            'description':     'Genehmigung eines Urlaubs- oder Stornierungsantrags durch das '
                               'Ausbildungsreferat und anschließende Bearbeitung durch die '
                               'Urlaubsstelle.',
            'is_active':       True,
            'reject_behavior': 'final',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Genehmigung durch Ausbildungsreferat',
            approver_type='role',
            approver_value='training_office',
            deadline_days=5,
            on_timeout='escalate_to',
            escalate_to_value='training_director',
        )
        WorkflowStep.objects.create(
            workflow=wd,
            order=2,
            name='Bearbeitung durch Urlaubsstelle',
            approver_type='role',
            approver_value='holiday_office',
            deadline_days=10,
            on_timeout='remind',
        )


def remove_vacation_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(code='vacation_request').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0002_seed_default_workflows'),
    ]

    operations = [
        migrations.RunPython(seed_vacation_workflow, reverse_code=remove_vacation_workflow),
    ]
