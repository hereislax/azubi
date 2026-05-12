# Generated for BITV-2.0-Konformität: Erklärung zur Barrierefreiheit (Pflichtfeld)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_alter_notificationtemplate_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='barrierefreiheit_text',
            field=models.TextField(
                blank=True,
                help_text='Pflichtangaben nach BITV 2.0 §12 / EU 2016/2102: Konformitätsstatus, '
                          'nicht barrierefreie Inhalte, Feedback-Kontakt, Schlichtungsstelle. '
                          'HTML erlaubt. Bleibt leer → Default-Vorlage wird gerendert.',
                verbose_name='Erklärung zur Barrierefreiheit',
            ),
        ),
    ]
