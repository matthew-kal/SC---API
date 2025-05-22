from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'surgicalm.users'

    def ready(self):
            import surgicalm.users.signals
