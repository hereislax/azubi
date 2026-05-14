from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workflow'
    verbose_name = 'Genehmigungs-Workflows'

    def ready(self):
        # Standard-Rollen aus services.roles für die Engine registrieren.
        from services import roles
        from . import approvers

        approvers.register_role('training_director',     roles.is_training_director)
        approvers.register_role('training_office',       roles.is_training_office)
        approvers.register_role('training_coordinator',  roles.is_training_coordinator)
        approvers.register_role('holiday_office',
            lambda u: u.is_authenticated and u.groups.filter(name='urlaubsstelle').exists())
        approvers.register_role('dormitory_management', roles.is_dormitory_management)
        approvers.register_role('travel_expense_office', roles.is_travel_expense_office)

        # Modul-spezifische dynamische Resolver werden in den jeweiligen apps.py
        # registriert (z.B. proofoftraining.apps.ready()).
