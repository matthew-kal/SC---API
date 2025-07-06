import requests
from itertools import islice
from django.core.management.base import BaseCommand
from surgicalm.users.models import PushNotificationToken

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'

def chunked(iterable, size):
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk


class Command(BaseCommand):
    help = 'Send push notifications to all registered users'

    def add_arguments(self, parser):
        parser.add_argument('--title', type=str, default='Daily Reminder 🚀', help='Notification title')
        parser.add_argument('--body', type=str, default='Time to check your app!', help='Notification body')

    def handle(self, *args, **options):
        tokens = list(PushNotificationToken.objects.values_list('token', flat=True))

        if not tokens:
            self.stdout.write(self.style.WARNING("⚠️ No push tokens found."))
            return

        title = options['title']
        body = options['body']
        success_count = 0
        fail_count = 0

        for batch in chunked(tokens, 100):
            messages = [{
                'to': token,
                'title': title,
                'body': body,
                'sound': 'default',
            } for token in batch]

            response = requests.post(EXPO_PUSH_URL, json=messages, headers={'Content-Type': 'application/json'})

            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"❌ Failed to send batch: {response.text}"))
                continue

            results = response.json().get('data', [])
            for i, result in enumerate(results):
                token = batch[i]
                if result.get('status') == 'ok':
                    success_count += 1
                else:
                    fail_count += 1
                    error = result.get('message')
                    self.stdout.write(self.style.WARNING(f"⚠️ Token error [{token}]: {error}"))

                    if result.get('details', {}).get('error') == 'DeviceNotRegistered':
                        PushNotificationToken.objects.filter(token=token).delete()
                        self.stdout.write(self.style.NOTICE(f"Removed unregistered token: {token}"))

        self.stdout.write(self.style.SUCCESS(f"✅ {success_count} notifications sent successfully."))
        if fail_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠️ {fail_count} notifications failed."))