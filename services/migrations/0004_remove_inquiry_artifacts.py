# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.db import migrations


INQUIRY_KEYS = ['inquiry_new', 'inquiry_reply']
INQUIRY_WIDGET_ID = 'open_inquiries'


def remove_inquiry_artifacts(apps, schema_editor):
    NotificationTemplate = apps.get_model('services', 'NotificationTemplate')
    NotificationTemplate.objects.filter(key__in=INQUIRY_KEYS).delete()

    DashboardConfig = apps.get_model('services', 'DashboardConfig')
    for cfg in DashboardConfig.objects.all():
        changed = False
        if cfg.widget_order and INQUIRY_WIDGET_ID in cfg.widget_order:
            cfg.widget_order = [w for w in cfg.widget_order if w != INQUIRY_WIDGET_ID]
            changed = True
        if cfg.hidden_widgets and INQUIRY_WIDGET_ID in cfg.hidden_widgets:
            cfg.hidden_widgets = [w for w in cfg.hidden_widgets if w != INQUIRY_WIDGET_ID]
            changed = True
        if changed:
            cfg.save(update_fields=['widget_order', 'hidden_widgets'])


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0003_alter_userprofile_options'),
    ]

    operations = [
        migrations.RunPython(remove_inquiry_artifacts, migrations.RunPython.noop),
    ]
