import requests
from django.core.management.base import BaseCommand
from users.models import PushNotificationToken

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'

class Command(BaseCommand):
    help = 'Send push notifications to all registered users'

    def handle(self, *args, **kwargs):
        """Send push notifications to all users with a stored token."""
        tokens = PushNotificationToken.objects.values_list('token', flat=True)

        if not tokens:
            self.stdout.write(self.style.WARNING("⚠️ No push tokens found."))
            return

        messages = [{
            'to': token,
            'title': 'Daily Reminder 🚀',
            'body': 'Time to check your app!',
            'data': {'screen': 'HomeScreen'}
        } for token in tokens]

        response = requests.post(EXPO_PUSH_URL, json=messages, headers={'Content-Type': 'application/json'})

        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS("✅ Notifications sent successfully!"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed to send notifications: {response.text}"))