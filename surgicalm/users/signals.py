from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import *

@receiver(post_save, sender=CustomUser)
def create_special_video(sender, instance, created, **kwargs):
    if created and instance.user_type == 'patient':
        DataCollection.objects.create(patient=instance)
