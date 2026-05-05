# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Initialdaten in die Datenbank einspielen (idempotent via get_or_create).

Dieser Command ersetzt die historischen RunPython-Seed-Migrationen, die beim
Squashen der Migrationen am 2026-05-03 entfernt wurden.

    python manage.py seed_defaults

Setzt:
- auth.Group: ausbildungsleitung, ausbildungskoordination, ausbildungsreferat
- services.Gender: m / w / d
- services.NotificationTemplate: alle Defaults aus NOTIFICATION_DEFAULTS
- student.Status: aktiv / abgeschlossen / abgebrochen
- student.Employment: Neueinstellung (B) / (TB)
- course.Career: mD / gD / hD
- assessment.StationFeedbackCategory: 7 Stationsfeedback-Kategorien
- django_celery_beat: PeriodicTasks für Pflichtschulungs- + SiteConfig-Tasks
"""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


GROUPS = ('ausbildungsleitung', 'ausbildungskoordination', 'ausbildungsreferat')

GENDERS = [
    ('m', 'männlich', 'Herr'),
    ('w', 'weiblich', 'Frau'),
    ('d', 'divers',   ''),
]

STATUSES = [
    {'description': 'aktiv',         'color': 'success'},
    {'description': 'abgeschlossen', 'color': 'secondary'},
    {'description': 'abgebrochen',   'color': 'danger'},
]

EMPLOYMENTS = [
    'Neueinstellung (B)',
    'Neueinstellung (TB)',
]

CAREERS = [
    ('mD', 'mittlerer Dienst'),
    ('gD', 'gehobener Dienst'),
    ('hD', 'höherer Dienst'),
]

STATION_FEEDBACK_CATEGORIES = [
    {'name': 'einarbeitung_betreuung',         'label': 'Einarbeitung & Betreuung',         'help_text': 'Ich wurde gut eingearbeitet und habe ausreichend Unterstützung erhalten.',                  'order': 1},
    {'name': 'aufgabenvielfalt_praxisbezug',   'label': 'Aufgabenvielfalt & Praxisbezug',   'help_text': 'Die Aufgaben waren abwechslungsreich und hatten einen klaren Bezug zur Ausbildung.',       'order': 2},
    {'name': 'lernmoeglichkeiten_entwicklung', 'label': 'Lernmöglichkeiten & Entwicklung',  'help_text': 'Ich konnte neue Fähigkeiten entwickeln und Verantwortung übernehmen.',                     'order': 3},
    {'name': 'teamklima_kommunikation',        'label': 'Teamklima & Kommunikation',        'help_text': 'Das Arbeitsklima war angenehm und die Kommunikation im Team offen und respektvoll.',     'order': 4},
    {'name': 'organisation_arbeitsstruktur',   'label': 'Organisation & Arbeitsstruktur',   'help_text': 'Abläufe und Strukturen in der Organisationseinheit waren klar und nachvollziehbar.',     'order': 5},
    {'name': 'ausbildungsrelevanz',            'label': 'Ausbildungsrelevanz',              'help_text': 'Der Praxisabschnitt hat meine berufliche Entwicklung sinnvoll gefördert.',                 'order': 6},
    {'name': 'gesamtzufriedenheit',            'label': 'Gesamtzufriedenheit',              'help_text': 'Ich war insgesamt mit meinem Praxisabschnitt in dieser Organisationseinheit zufrieden.', 'order': 7},
]


class Command(BaseCommand):
    help = "Spielt Initialdaten (Gruppen, Geschlechter, Status, Karrieren, etc.) idempotent ein."

    def handle(self, *args, **options):
        self._seed_groups()
        self._seed_genders()
        self._seed_notification_templates()
        self._seed_student_status()
        self._seed_employment()
        self._seed_careers()
        self._seed_station_feedback_categories()
        self._seed_periodic_tasks()
        self.stdout.write(self.style.SUCCESS("Seed abgeschlossen."))

    # ── Auth-Gruppen ──────────────────────────────────────────────────────

    def _seed_groups(self):
        created = 0
        for name in GROUPS:
            _, was_created = Group.objects.get_or_create(name=name)
            created += int(was_created)
        self.stdout.write(f"  Auth-Gruppen: +{created} neu, {len(GROUPS) - created} vorhanden")

    # ── Geschlechter ──────────────────────────────────────────────────────

    def _seed_genders(self):
        from services.models import Gender
        created = 0
        for abbr, gender, description in GENDERS:
            _, was_created = Gender.objects.get_or_create(
                abbreviation=abbr,
                defaults={'gender': gender, 'description': description},
            )
            created += int(was_created)
        self.stdout.write(f"  Geschlechter: +{created} neu, {len(GENDERS) - created} vorhanden")

    # ── Notification-Templates ────────────────────────────────────────────

    def _seed_notification_templates(self):
        from services.models import NOTIFICATION_DEFAULTS, NotificationTemplate
        created = 0
        for key, defaults in NOTIFICATION_DEFAULTS.items():
            _, was_created = NotificationTemplate.objects.get_or_create(key=key, defaults=defaults)
            created += int(was_created)
        total = len(NOTIFICATION_DEFAULTS)
        self.stdout.write(f"  Notification-Templates: +{created} neu, {total - created} vorhanden")

    # ── Student-Status ────────────────────────────────────────────────────

    def _seed_student_status(self):
        from student.models import Status
        created = 0
        for entry in STATUSES:
            _, was_created = Status.objects.get_or_create(
                description=entry['description'],
                defaults={'color': entry['color']},
            )
            created += int(was_created)
        self.stdout.write(f"  Student-Status: +{created} neu, {len(STATUSES) - created} vorhanden")

    # ── Beschäftigungsverhältnisse ────────────────────────────────────────

    def _seed_employment(self):
        from student.models import Employment
        created = 0
        for description in EMPLOYMENTS:
            _, was_created = Employment.objects.get_or_create(description=description)
            created += int(was_created)
        self.stdout.write(f"  Employment: +{created} neu, {len(EMPLOYMENTS) - created} vorhanden")

    # ── Laufbahnen ────────────────────────────────────────────────────────

    def _seed_careers(self):
        from course.models import Career
        created = 0
        for abbr, description in CAREERS:
            _, was_created = Career.objects.get_or_create(
                abbreviation=abbr,
                defaults={'description': description},
            )
            created += int(was_created)
        self.stdout.write(f"  Laufbahnen: +{created} neu, {len(CAREERS) - created} vorhanden")

    # ── Stationsfeedback-Kategorien ───────────────────────────────────────

    def _seed_station_feedback_categories(self):
        from assessment.models import StationFeedbackCategory
        created = 0
        for cat in STATION_FEEDBACK_CATEGORIES:
            _, was_created = StationFeedbackCategory.objects.get_or_create(
                name=cat['name'],
                defaults={
                    'label': cat['label'],
                    'help_text': cat['help_text'],
                    'order': cat['order'],
                    'active': True,
                },
            )
            created += int(was_created)
        total = len(STATION_FEEDBACK_CATEGORIES)
        self.stdout.write(f"  Stationsfeedback-Kategorien: +{created} neu, {total - created} vorhanden")

    # ── Celery-Beat PeriodicTasks ─────────────────────────────────────────

    def _seed_periodic_tasks(self):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask
        from services.models import SiteConfiguration

        # 1. Pflichtschulungs-Erinnerungen
        daily, _ = CrontabSchedule.objects.get_or_create(
            minute='30', hour='7',
            day_of_week='*', day_of_month='*', month_of_year='*',
            timezone='Europe/Berlin',
        )
        weekly_mon, _ = CrontabSchedule.objects.get_or_create(
            minute='0', hour='8',
            day_of_week='1', day_of_month='*', month_of_year='*',
            timezone='Europe/Berlin',
        )
        PeriodicTask.objects.update_or_create(
            name='pflichtschulungen-erinnerungen-azubi',
            defaults={
                'task': 'mandatorytraining.send_expiry_reminders',
                'crontab': daily, 'interval': None, 'enabled': True,
            },
        )
        PeriodicTask.objects.update_or_create(
            name='pflichtschulungen-sammelmail-referat',
            defaults={
                'task': 'mandatorytraining.send_overdue_summary',
                'crontab': weekly_mon, 'interval': None, 'enabled': True,
            },
        )

        # 2. Tasks aus SiteConfiguration via beat_sync
        config = SiteConfiguration.objects.first()
        if config is None:
            config = SiteConfiguration.get()  # legt Singleton an
        try:
            from services.beat_sync import sync_periodic_tasks
            sync_periodic_tasks(config)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  beat_sync Fehler: {exc}"))

        self.stdout.write("  Celery-Beat PeriodicTasks: aktualisiert")
