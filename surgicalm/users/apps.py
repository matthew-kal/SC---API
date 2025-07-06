from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'surgicalm.users'
    label = 'users' # <--- ADD THIS LINE: Explicitly define the app_label
    verbose_name = 'User Management' # Optional: good for Django admin

    def ready(self):
        # Import signals here to ensure they are connected when the app is ready
        import surgicalm.users.signals