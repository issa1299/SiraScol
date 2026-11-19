from django.apps import AppConfig


class ProfConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'prof'
    verbose_name = 'Espace Professeur'

    def ready(self):
        from . import signals  # noqa: F401
