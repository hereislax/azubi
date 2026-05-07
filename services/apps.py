# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.apps import AppConfig


class ServicesConfig(AppConfig):
    name = 'services'
    verbose_name = 'System & Konfiguration'

    def ready(self):
        from django.db.models.signals import post_save, pre_save
        from django.contrib.auth.models import User
        from django.contrib.auth.signals import user_logged_in

        def create_user_profile(sender, instance, created, **kwargs):
            if created:
                from services.models import UserProfile
                UserProfile.objects.get_or_create(user=instance)

        post_save.connect(create_user_profile, sender=User)

        def sync_beat_on_config_save(sender, instance, **kwargs):
            from services.beat_sync import sync_periodic_tasks
            sync_periodic_tasks(instance)

        from services.models import SiteConfiguration
        post_save.connect(sync_beat_on_config_save, sender=SiteConfiguration)

        def expire_session_at_workday_end(sender, request, user, **kwargs):
            """Setzt die Session-Lebensdauer auf heute 18:00 Europe/Berlin."""
            from datetime import datetime, time, timedelta
            from zoneinfo import ZoneInfo
            tz = ZoneInfo('Europe/Berlin')
            now = datetime.now(tz)
            cutoff = datetime.combine(now.date(), time(18, 0), tzinfo=tz)
            if now < cutoff:
                request.session.set_expiry(cutoff)
            else:
                request.session.set_expiry(datetime.combine(now.date() + timedelta(days=1), time(18, 0), tzinfo=tz))

        user_logged_in.connect(expire_session_at_workday_end)

        # Ein User darf höchstens eine externe Identität (= eine Behörden-IdP-
        # Verknüpfung) besitzen. allauth kennt diese Regel nicht, also erzwingen
        # wir sie hier vor dem Speichern.
        from allauth.socialaccount.models import SocialAccount
        from django.core.exceptions import ValidationError

        def enforce_one_external_identity_per_user(sender, instance, **kwargs):
            if instance.pk is not None:
                return  # Update auf bestehender Verknüpfung – ok
            if SocialAccount.objects.filter(user=instance.user).exists():
                raise ValidationError(
                    f'Der Benutzer "{instance.user}" hat bereits eine externe '
                    f'Identität verknüpft. Bestehende Verknüpfung erst lösen.'
                )

        pre_save.connect(
            enforce_one_external_identity_per_user,
            sender=SocialAccount,
        )
