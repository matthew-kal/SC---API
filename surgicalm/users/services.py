from django.db import models
from django.utils import timezone
from random import randint
from .models import (
    AssignedModules, AssignedTask, AssignedQuote, 
    DailyModuleCategories, ModulesList, TaskList, 
    Quotes, UserVideoRefresh
)


def refresh_user_data(user):
    """Helper function to refresh user data."""

    hospital = user.hospital
    
    # Step 1: Delete Existing Entries
    AssignedModules.objects.filter(patient=user).delete()
    AssignedTask.objects.filter(patient=user).delete()
    AssignedQuote.objects.filter(patient=user).delete()

    # Step 2: Retrieve Selected Categories and Subcategories
    categories = DailyModuleCategories.objects.filter(hospital=hospital).values('category', 'subcategory')

    # Step 3: Assign New Videos
    for category_entry in categories:
        category = category_entry['category']
        subcategory = category_entry['subcategory']
        print("Daily Modules Running")
        
        videos_queryset = ModulesList.objects.filter(
            category_id=category, 
            subcategory_id=subcategory, 
            hospital=hospital
        )
        count = videos_queryset.count()
        if count > 0:
            random_index = randint(0, count - 1)
            random_video = videos_queryset.all()[random_index]
            AssignedModules.objects.create(patient=user, video=random_video, isCompleted=False)
            print("Daily Modules Added")

    # Step 4: Assign New Tasks
    tasks = TaskList.objects.filter(hospital=hospital)  
    for task in tasks:
        AssignedTask.objects.create(patient=user, task=task, isCompleted=False)  
        print("Daily Task Added")

    # Step 5: Assign New Quote
    random_quote = None
    count = Quotes.objects.count()
    if count > 0:
        random_index = randint(0, count - 1)
        random_quote = Quotes.objects.all()[random_index]
        AssignedQuote.objects.create(patient=user, quote=random_quote)
        print("Daily Quote Added")

    # Step 6: Update Refresh Date
    user_refresh = UserVideoRefresh.objects.filter(patient=user).first()
    if user_refresh:
        user_refresh.last_refreshed = timezone.now().date()
        user_refresh.save()
    else:
        UserVideoRefresh.objects.create(patient=user, last_refreshed=timezone.now().date()) 