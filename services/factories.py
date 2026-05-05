# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Factory-Boy-Factories. Pro App eine eigene factories.py anlegen und hier
nur die domain-übergreifenden Basics (User) bereitstellen."""
import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name", locale="de_DE")
    last_name = factory.Faker("last_name", locale="de_DE")
    is_active = True


class AdminUserFactory(UserFactory):
    is_staff = True
    is_superuser = True
    username = factory.Sequence(lambda n: f"admin{n}")