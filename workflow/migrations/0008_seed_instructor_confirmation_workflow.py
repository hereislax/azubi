"""Daten-Migration: Workflow für die Bestätigung neuer Praxistutoren.

Eine Stufe:
- Bestätigung durch die Ausbildungsleitung (Frist 5 Tage, Erinnerung bei
  Überschreitung).

Per Workshop-Entscheidung (1-stufig, keine Eskalation, einheitlicher Workflow
für alle Praxistutoren).

Reject-Verhalten: ``final``. Wenn ein angelegter Praxistutor doch nicht
bestätigt werden soll, wird der Datensatz gelöscht (siehe ``instructor_delete``);
der Workflow wird in diesem Fall vom Mirror als „cancelled" markiert.
"""
from django.db import migrations


def seed_instructor_confirmation_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    wd, created = WorkflowDefinition.objects.get_or_create(
        code='instructor_confirmation',
        defaults={
            'name':            'Praxistutor-Bestellung',
            'description':     'Neu angelegte Praxistutoren werden von der Ausbildungsleitung '
                               'bestätigt; im Anschluss wird automatisch ein '
                               'Bestellungsschreiben versandt.',
            'is_active':       True,
            'reject_behavior': 'final',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Bestätigung durch Ausbildungsleitung',
            approver_type='role',
            approver_value='training_director',
            deadline_days=5,
            on_timeout='remind',
        )


def remove_instructor_confirmation_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(code='instructor_confirmation').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0007_seed_change_request_workflow'),
    ]

    operations = [
        migrations.RunPython(seed_instructor_confirmation_workflow,
                              reverse_code=remove_instructor_confirmation_workflow),
    ]
