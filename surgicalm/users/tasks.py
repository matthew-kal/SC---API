from celery import shared_task
from .services import refresh_user_data
from .models import CustomUser
import logging

logger = logging.getLogger(__name__)

@shared_task
def refresh_daily_data_for_user(user_id):
    """
    Celery task to refresh daily data for a single user.
    """
    logger.info(f"🚀 STARTING: refresh_daily_data_for_user for user {user_id}")
    print(f"🚀 STARTING: refresh_daily_data_for_user for user {user_id}")
    
    try:
        user = CustomUser.objects.get(id=user_id)
        logger.info(f"📊 Found user {user_id}, calling refresh_user_data")
        print(f"📊 Found user {user_id}, calling refresh_user_data")
        
        refresh_user_data(user) # Calling the function from services.py
        
        logger.info(f"✅ SUCCESS: refreshed data for user {user_id}")
        print(f"✅ SUCCESS: refreshed data for user {user_id}")
        return f"Successfully refreshed data for user {user_id}"
    except CustomUser.DoesNotExist:
        error_msg = f"❌ ERROR: User with id {user_id} not found."
        logger.error(error_msg)
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ EXCEPTION: Error refreshing user {user_id}: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        return error_msg