from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.timezone import now
from django.conf import settings

class PartnerHospitals(models.Model):
    hospital_name = models.CharField(max_length=255, unique=True, null=False, blank=False)

    class Meta:
        app_label = 'users'

class CustomUser(AbstractUser):
    
    USER_TYPE_CHOICES = (
        ('nurse', 'Nurse'),   
        ('patient', 'Patient'),
    )
    
    user_type = models.CharField(max_length = 10, choices = USER_TYPE_CHOICES, null=False, blank=False)
    hospital = models.ForeignKey(PartnerHospitals, on_delete=models.CASCADE, null=False, blank=False)
    
    class Meta(AbstractUser.Meta):
        indexes = [
            models.Index(fields=['hospital', 'user_type']),
        ]    

class Quotes(models.Model):
    Quote = models.CharField(max_length=255, null=False, blank=False, unique=True) 
    
class TaskList(models.Model): 
    taskName = models.CharField(max_length= 100, null=False, blank=False)
    taskDesc = models.CharField(max_length= 100, null=False, blank=False)
    hospital = models.ForeignKey(PartnerHospitals, on_delete=models.CASCADE, null=False, blank=False)  
    icon = models.CharField(max_length=255, default="alarm-outline")

class ModuleCategories(models.Model):
    category = models.CharField(max_length=255, null=False, blank=False)
    icon = models.CharField(max_length=255, null=False, blank=False)
    hospital = models.ForeignKey(PartnerHospitals, on_delete=models.CASCADE, null=False, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['hospital', 'category', 'icon'], name='unique_per_hospital')
        ]
    
class ModuleSubcategories(models.Model):
    subcategory = models.CharField(max_length=255, null=False, blank=False)
    category = models.ForeignKey(ModuleCategories, on_delete=models.CASCADE, null=False, blank=False)
    hospital = models.ForeignKey(PartnerHospitals, on_delete=models.CASCADE, null=False, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['category', 'subcategory'], name='unique_subcategory_per_category')
        ]

class ModulesList(models.Model):

    MEDIA_CHOICES = (
        ('video', 'Video'),
        ('audio', 'Audio'),
    )

    hospital = models.ForeignKey(PartnerHospitals, on_delete=models.CASCADE, null=False, blank=False)
    category = models.ForeignKey(ModuleCategories, on_delete=models.CASCADE, null=False, blank=False)
    subcategory = models.ForeignKey(ModuleSubcategories, on_delete=models.CASCADE, null=False, blank=False)
    title = models.CharField(max_length=255, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    url = models.URLField(null=False, blank=False)
    media_type   = models.CharField(max_length=5, choices=MEDIA_CHOICES, default='video', null=False, blank=False)

class DailyModuleCategories(models.Model):
    category = models.ForeignKey(ModuleCategories, on_delete=models.CASCADE, null=False, blank=False)
    subcategory = models.ForeignKey(ModuleSubcategories, on_delete=models.CASCADE, null=False, blank=False)
    hospital = models.ForeignKey(PartnerHospitals, on_delete=models.CASCADE, null=False, blank=False)

class UserVideoRefresh(models.Model):
    patient = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    last_refreshed = models.DateTimeField(auto_now_add=True)

class AssignedModules(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False)
    video = models.ForeignKey(ModulesList, on_delete=models.CASCADE)
    isCompleted = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['patient', 'isCompleted']),
        ]

class AssignedQuote(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False)
    quote = models.ForeignKey(Quotes, on_delete=models.CASCADE)   

class AssignedTask(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False)
    task = models.ForeignKey(TaskList, on_delete=models.CASCADE)
    isCompleted = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['patient', 'isCompleted']),
        ]

class WatchedData(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=False, blank=False)
    video = models.ForeignKey(ModulesList, on_delete=models.CASCADE, null=False, blank=False)
    date = models.DateField(default=now, null=False, blank=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

class PushNotificationToken(models.Model):
    token = models.CharField(max_length=255, unique=True)
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)



