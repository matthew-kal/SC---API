from django.core.management.base import BaseCommand
from surgicalm.users.models import CustomUser
from surgicalm.users.tasks import refresh_daily_data_for_user

class Command(BaseCommand):
    help = 'Dispatches a Celery task to refresh daily data for all active patients.'

    def handle(self, *args, **options):
        patients = CustomUser.objects.filter(user_type='patient', is_active=True)
        self.stdout.write(f'Found {patients.count()} active patients to refresh.')

        for user in patients:
            refresh_daily_data_for_user.delay(user.id)
            self.stdout.write(f'Dispatched refresh task for user: {user.id}')

        self.stdout.write(self.style.SUCCESS('All refresh tasks have been dispatched.'))