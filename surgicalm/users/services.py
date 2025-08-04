import logging
from django.db import models
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from random import randint

logger = logging.getLogger(__name__)
from .models import (
    AssignedModules, AssignedTask, AssignedQuote, 
    DailyModuleCategories, ModulesList, TaskList, 
    Quotes, UserVideoRefresh, WatchedData
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
        logger.debug("Assigning daily modules for user %s", user.id)
        
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
            logger.info("Assigned module %s to user %s", random_video.id, user.id)

    # Step 4: Assign New Tasks
    tasks = TaskList.objects.filter(hospital=hospital)  
    for task in tasks:
        AssignedTask.objects.create(patient=user, task=task, isCompleted=False)  
        logger.info("Assigned task %s to user %s", task.id, user.id)

    # Step 5: Assign New Quote
    random_quote = None
    count = Quotes.objects.count()
    if count > 0:
        random_index = randint(0, count - 1)
        random_quote = Quotes.objects.all()[random_index]
        AssignedQuote.objects.create(patient=user, quote=random_quote)
        logger.info("Assigned quote %s to user %s", random_quote.id, user.id)

    # Step 6: Update Refresh Date
    user_refresh = UserVideoRefresh.objects.filter(patient=user).first()
    if user_refresh:
        user_refresh.last_refreshed = timezone.now().date()
        user_refresh.save()
    else:
        UserVideoRefresh.objects.create(patient=user, last_refreshed=timezone.now().date())


def calculate_weekly_watched_data(user):
    """Helper function to calculate weekly watched data for a user."""
    today = timezone.now().date()
    start_of_week = today - timezone.timedelta(days=today.weekday())

    watched_entries = WatchedData.objects.filter(user=user, date__gte=start_of_week)
    counts_by_day = watched_entries.annotate(day=TruncDate('date')).values('day').annotate(count=Count('id'))

    day_map = {i: day for i, day in enumerate(['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun'])}
    week_data = {day: 0 for day in day_map.values()}

    for entry in counts_by_day:
        weekday = entry['day'].weekday()
        day_label = day_map.get(weekday)
        if day_label:
            week_data[day_label] = entry['count']

    week_data['week'] = sum(week_data.values())
    week_data['all_time'] = WatchedData.objects.filter(user=user).count()
    return week_data 