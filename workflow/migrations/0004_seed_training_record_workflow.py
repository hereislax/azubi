"""Daten-Migration: legt den Workflow für Ausbildungsnachweise an.

Eine Stufe:
- Prüfung durch Ausbildungsleitung / Ausbildungsverantwortliche (Frist 7 Tage,
  Erinnerung bei Überschreitung).

Reject-Verhalten: ``to_initiator`` — bei Ablehnung sieht die Nachwuchskraft
die Korrekturhinweise, überarbeitet den Nachweis und reicht ihn erneut ein
(Revision wird hochgezählt; alle Transitionen bleiben im Audit-Trail).

Die optionale Vorstufe „Bestätigung durch aktuellen Praxistutor" kann später
über die Workflow-Verwaltung ergänzt werden (Approver-Typ ``external_token``).
"""
from django.db import migrations


def seed_training_record_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowStep       = apps.get_model('workflow', 'WorkflowStep')

    wd, created = WorkflowDefinition.objects.get_or_create(
        code='training_record',
        defaults={
            'name':            'Ausbildungsnachweis',
            'description':     'Wöchentlicher Ausbildungsnachweis einer Nachwuchskraft. '
                               'Bei Ablehnung kehrt der Nachweis zur Überarbeitung an die '
                               'Nachwuchskraft zurück; nach Resubmit läuft der Workflow '
                               'erneut durch.',
            'is_active':       True,
            'reject_behavior': 'to_initiator',
        },
    )
    if created:
        WorkflowStep.objects.create(
            workflow=wd,
            order=1,
            name='Prüfung durch Ausbildungsleitung',
            approver_type='role',
            approver_value='training_director',
            deadline_days=7,
            on_timeout='remind',
        )


def remove_training_record_workflow(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    WorkflowDefinition.objects.filter(code='training_record').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0003_seed_vacation_workflow'),
    ]

    operations = [
        migrations.RunPython(seed_training_record_workflow,
                              reverse_code=remove_training_record_workflow),
    ]
