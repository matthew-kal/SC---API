
import logging
import time  # for constant‑time response padding



# Standard library imports
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetCompleteView, PasswordResetDoneView
from django.conf import settings
from django.db import transaction
from django.db.models.functions import TruncDate
from django.db.models import Count

# Third-party imports
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from axes.decorators import axes_dispatch
from django_ratelimit.decorators import ratelimit
from django_ratelimit.core import is_ratelimited

# Local (project-specific) imports
from surgicalm.users.models import *  
from surgicalm.users.auth import *
from surgicalm.users.serializers import *

# Logger
logger = logging.getLogger(__name__)

# User Model 
User = get_user_model()



# ADMIN FUNCTIONS

@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='none', rate='5/h', method='POST', block=True)
def create_nurse(request):
    """Registers a nurse with an assigned hospital if a valid dev key is provided"""

    dev_serializer = DevSerializer(data=request.data)
    if not dev_serializer.is_valid():
        return Response({"error": "Invalid developer key format."}, status=status.HTTP_400_BAD_REQUEST)
    
    dev_key = dev_serializer.validated_data['dev_key']
    if not auth_dev(dev_key):  
        return Response({"error": "Unauthorized: Invalid developer key."}, status=status.HTTP_401_UNAUTHORIZED)

    nurse_serializer = NurseRegistrationSerializer(data=request.data)
    if nurse_serializer.is_valid():
        nurse_serializer.save()
        return Response({"message": "Nurse registration successful."}, status=status.HTTP_201_CREATED)

    return Response(nurse_serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# AUTH (NURSE & PATIENT)

@api_view(['POST'])
@permission_classes([AllowAny])
@axes_dispatch
def nurse_login(request):
    serializer = NurseLoginSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = auth_nurse(username=username, password=password, request=request)  
        if user:  
            refresh = RefreshToken.for_user(user) 
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@axes_dispatch  
def patient_login(request):
    serializer = PatientLoginSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = auth_patient(username=username, password=password, request=request)         
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user_or_ip', rate='20/h', method='POST', block=True)
def patient_register(request):
    """
    Create a new patient account under the nurse's hospital.
    Rate-limited (20 per hour per nurse or IP).
    Returns HTTP 201 with the new patient id and a Location header.
    """
    if request.user.user_type != "nurse":
        return Response(
            {"message": "Only nurses can register patients."},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = PatientRegistrationSerializer(
        data=request.data,
        context={'hospital': request.user.hospital}
    )

    if serializer.is_valid():
        patient = serializer.save()                     # password validation happens in serializer
        logger.info("Nurse %s created patient %s", request.user.id, patient.id)

        # Build a Location header if you have a detail route; fallback to a sensible URL otherwise
        try:
            location = reverse('patient_detail', kwargs={'pk': patient.id})
        except Exception:
            location = f"/users/patient/{patient.id}/"

        return Response(
            {"id": patient.id, "message": "Registration successful"},
            status=status.HTTP_201_CREATED,
            headers={'Location': location}
        )

    # Log and format errors
    errors = serializer.errors
    formatted_errors = " ".join(" ".join(errs) for errs in errors.values())
    logger.warning("Patient registration failed: %s", formatted_errors)

    return Response(
        {"message": formatted_errors, "errors": errors},
        status=status.HTTP_400_BAD_REQUEST
    )

@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='5/h', method='POST', block=False)
def request_password_reset(request):
    """
    Send a password‑reset email *if and only if* the user exists, but
    take roughly the same amount of time whether or not the e‑mail is registered.
    This prevents timing‑based account enumeration attacks.
    """
    start_time = time.monotonic()          # ── begin timer for constant‑time padding

    # Ratelimit #1: IP-based
    if getattr(request, 'limited', False):
        return Response(
            {'message': 'Too many requests from this IP. Try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    email = request.data.get('email', '').lower().strip()
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    # Ratelimit #2: Per‑email (shared cache)
    if is_ratelimited(request=request, key=lambda r: email, rate='2/h',
                      method='POST', increment=True):
        return Response(
            {'message': 'Too many requests for this account. Try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        user = CustomUser.objects.filter(email__iexact=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = f"{settings.BASE_URL}/password-reset-confirm/{uid}/{token}/"

            send_mail(
                subject="Password Reset",
                message=f"Use the link below to reset your password:\n{reset_link}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
    except Exception as e:
        logger.error(f"Error in password-reset flow for {email}: {e}")

    # Constant‑time padding ─ ensure every call lasts at least ~0.5 s
    elapsed = time.monotonic() - start_time
    if elapsed < 0.5:
        time.sleep(0.5 - elapsed)

    return Response(
        {'message': 'If that account exists, a password reset link has been sent.'},
        status=status.HTTP_200_OK,
    )

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'templates/password_reset_complete.html'
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'templates/password_reset_done.html'

#NURSE

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_patients(request):
    search_query = request.GET.get('query', '')
    search_by = request.GET.get('searchBy', 'username')
    hospital = request.user.hospital

    queryset = CustomUser.objects.filter(user_type='patient')

    if search_by == 'id':
        try:
            patients = queryset.filter(id=search_query, hospital=hospital)
        except CustomUser.DoesNotExist:
            return Response({"error": "Patient not found"}, status=status.HTTP_200_OK)
    elif search_by == 'email':
        patients = queryset.filter(email__icontains=search_query, hospital=hospital)
    else:  
        patients = queryset.filter(username__icontains=search_query, hospital=hospital)
        
    if not patients.exists():
        return Response({"error": "No patients found"}, status=status.HTTP_200_OK)

    serializer = UserSerializer(patients, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_graph(request, id):
    try:
        today = timezone.now().date()
        start_of_week = today - timezone.timedelta(days=today.weekday())  # Monday

        watched_entries = WatchedData.objects.filter(user_id=id, date__gte=start_of_week)
        counts_by_day = watched_entries.annotate(day=TruncDate('date')).values('day').annotate(count=Count('id'))

        day_map = {i: day for i, day in enumerate(['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun'])}
        week_data = {day: 0 for day in day_map.values()}

        for entry in counts_by_day:
            weekday = entry['day'].weekday() 
            day_label = day_map.get(weekday)
            if day_label:
                week_data[day_label] = entry['count']

        week_data['week'] = sum(week_data.values())
        week_data['all_time'] = WatchedData.objects.filter(user_id=id).count()

        return Response({'weekData': week_data}, status=status.HTTP_200_OK)

    except ObjectDoesNotExist:
        return Response({'error': 'No data found for the specified patient.'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    

# PATIENT

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def category_list(request):
    """Returns all categories, their IDs, and icons for the requester's hospital."""
    
    user_hospital = request.user.hospital
    if user_hospital is None:
        return Response({"error": "User is not associated with any hospital."}, status=status.HTTP_400_BAD_REQUEST)
    categories = ModuleCategories.objects.filter(hospital=user_hospital).values("id", "category", "icon")
    return Response({"categories": list(categories)}, status=status.HTTP_200_OK)

    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subcategory_list(request, category_id):
    """Returns all subcategory names for a given category ID."""
    try:
        hospital = request.user.hospital

        if not ModuleCategories.objects.filter(id=category_id, hospital_id=hospital).exists():
            return Response({'error': 'Category not found for this hospital.'}, status=status.HTTP_404_NOT_FOUND)

        subcategories = list(ModuleSubcategories.objects.filter(category_id=category_id, hospital_id=hospital).values("id", "subcategory"))

        if not subcategories:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response({"subcategories": subcategories}, status=status.HTTP_200_OK)

    except ObjectDoesNotExist:
        return Response({'error': 'Database error: Unable to retrieve category data.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def modules_list(request, category, subcategory):

    try:
        videos = ModulesList.objects.filter(
            category_id=category, subcategory_id=subcategory, 
        ).values('id', 'title', 'url', 'category', 'subcategory', 'description', 'media_type')
        videos_list = list(videos)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    category_data = {
        'category': {
            'name': category,
            'subcategory': subcategory
        },
        'videos': videos_list,
    }
    
    return JsonResponse(category_data, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    user = request.user
    today_date = timezone.now().date()

    
    user_refresh = UserVideoRefresh.objects.filter(patient=user).first()
    
    
    if not user_refresh or user_refresh.last_refreshed.date() != today_date:
        print("Running Helper")
        refresh_user_data(request)

   
    general_videos = []
    tasks = []
    quote = {}

    assigned_videos = AssignedModules.objects.filter(patient=user).select_related("video")
    general_videos = [
        {
            "id": assigned_video.video.id,  
            "url": assigned_video.video.url, 
            "title": assigned_video.video.title,  
            "description": assigned_video.video.description,  
            "isCompleted": assigned_video.isCompleted,
            "icon": assigned_video.video.category.icon,
            "media_type": assigned_video.video.media_type,  
        }
        for assigned_video in assigned_videos
    ]

    # Step 4: Retrieve Assigned Tasks
    assigned_tasks = AssignedTask.objects.filter(patient=user).select_related("task")
    tasks = [
        {
            "id": assigned_task.task.id,  
            "name": assigned_task.task.taskName,  
            "description": assigned_task.task.taskDesc,  
            "isCompleted": assigned_task.isCompleted, 
            "icon": assigned_task.task.icon,
        }
        for assigned_task in assigned_tasks
    ]

    assigned_quote = AssignedQuote.objects.filter(patient=user).select_related("quote").first()

    quote = None
    if assigned_quote and assigned_quote.quote:
        quote = {
            "id": assigned_quote.quote.id, 
            "quote": assigned_quote.quote.Quote  
        }
    
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

    return Response({
        'generalVideos': general_videos or [], 
        'tasks': tasks or [], 
        'quote': quote or None, 
        'weekData': week_data or [],
    }, status=200)

def refresh_user_data(request):
    """Helper function to refresh user data."""

    user = request.user
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
        videos = ModulesList.objects.filter(
            category_id=category, 
            subcategory_id=subcategory, 
            hospital=hospital).order_by('?')
        if videos.exists():
            random_video = videos.first()
            # Ensure uniqueness
            if not AssignedModules.objects.filter(patient=user, video=random_video).exists():
                AssignedModules.objects.create(patient=user, video=random_video, isCompleted=False)
                print("Daily Modules Added")

    # Step 4: Assign New Tasks
    tasks = TaskList.objects.filter(hospital=hospital)  
    for task in tasks:
        # Ensure uniqueness
        if not AssignedTask.objects.filter(patient=user, task=task).exists():
            AssignedTask.objects.create(patient=user, task=task, isCompleted=False)  
            print("Daily Task Added")

    # Step 5: Assign New Quote
    random_quote = Quotes.objects.order_by('?').first()
    if random_quote:
        # Ensure uniqueness
        if not AssignedQuote.objects.filter(patient=user, quote=random_quote).exists():
            AssignedQuote.objects.create(patient=user, quote=random_quote)
            print("Daily Quote Added")

    # Step 6: Update Refresh Date
    user_refresh = UserVideoRefresh.objects.filter(patient=user).first()
    if user_refresh:
        user_refresh.last_refreshed = timezone.now().date()
        user_refresh.save()
    else:
        UserVideoRefresh.objects.create(patient=user, last_refreshed=timezone.now().date())  

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_task_completion(request, taskId):
    user = request.user  

    try:
        task_tracker = AssignedTask.objects.get(patient=user, task_id=taskId)

        task_tracker.isCompleted = True
        task_tracker.save()

        return Response({'message': 'Task completion status updated successfully.'}, status=status.HTTP_200_OK)

    except AssignedTask.DoesNotExist:
        return Response({'error': 'Assigned task not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_video_completion(request, videoId):
    user = request.user  

    if 'isCompleted' not in request.data:
        return Response({'error': "'isCompleted' field is required."}, status=status.HTTP_400_BAD_REQUEST)

    is_completed = request.data.get('isCompleted')

    try:
        with transaction.atomic():  
            
            video_tracker = AssignedModules.objects.get(patient=user, video_id=videoId)
            if video_tracker.isCompleted: 
                return Response({'message': 'Video has already been completed'}, status=status.HTTP_200_OK)
            video_tracker.isCompleted = is_completed
            video_tracker.save()

            if is_completed:
                WatchedData.objects.create(user=user, video=video_tracker.video, date=timezone.now().date())

            return Response({'message': 'Video completion status updated successfully.'}, status=status.HTTP_200_OK)

    except AssignedModules.DoesNotExist:
        return Response({'error': 'Assigned video not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

    except ObjectDoesNotExist:
        return Response({'error': 'Data collection record not found, failed to update statistics.'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

# Patient settings patient information
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    try:
        user = request.user

        if not user or not user.is_authenticated:
            return Response({'error': 'User not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)

        user_data = {
            "username": user.username,
            "id": user.id,
            "email": user.email,
        }

        return Response(user_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'error': 'Old password and new password are required'},
                    status=status.HTTP_400_BAD_REQUEST)

    user = request.user

    if not user.check_password(old_password):
        return Response({'error': 'Old password is incorrect'},
                    status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_password(new_password, user)
    except ValidationError as e:
        return Response({'errors': e.messages}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({'message': 'Password changed successfully'},
                status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@ratelimit(key="ip", rate="5/h", block=True)
def delete_account(request):
    """
    Hard-delete the authenticated user if the provided password is correct.
    JSON payload: { "password": "<current_password>" }
    """
    password = request.data.get("password", "")
    user = request.user

    if not password:
        return Response({"detail": "Password required."},
                        status=status.HTTP_400_BAD_REQUEST)

    if not user.check_password(password):
        return Response({"detail": "Incorrect password."},
                        status=status.HTTP_403_FORBIDDEN)

    with transaction.atomic():
        logger.info("User %s <%s> self-deleted account", user.id, user.email)
        user.delete()           

    return Response({"detail": "Account deleted."}, status=status.HTTP_204_NO_CONTENT)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_push_token(request):
    token = request.data.get('pushToken')
    if not token:
        return Response({'error': 'Missing pushToken'}, status=status.HTTP_400_BAD_REQUEST)
    PushNotificationToken.objects.update_or_create(token=token, defaults={'patient': request.user})
    return Response({'status': 'Token saved'}, status=status.HTTP_200_OK)

