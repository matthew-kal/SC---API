from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str  
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import make_password
from .models import *
from rest_framework_simplejwt.tokens import RefreshToken
from .auth import *
from .serializers import *
from django.utils import timezone
from django.contrib.auth.views import PasswordResetCompleteView
from django.contrib.auth.views import PasswordResetDoneView
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from axes.decorators import axes_dispatch 
from django.db import transaction






# ADMIN FUNCTIONS

@api_view(['POST'])
@permission_classes([AllowAny])
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
def patient_register(request):
    """Registers a new patient and assigns them to the nurse's hospital."""
    
    if request.user.user_type != "nurse":
        return Response(
            {"message": "Only nurses can register patients."},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = PatientRegistrationSerializer(data=request.data, context={'hospital': request.user.hospital})

    if serializer.is_valid():
        patient = serializer.save()
        patient.save()

        return Response({"message": "Registration successful"}, status=status.HTTP_201_CREATED)
    
    errors = serializer.errors
    formatted_errors = " ".join(
        f" {' '.join(error_list)}" for field , error_list in errors.items()
    )
    print(formatted_errors)

    return Response({
        "message": f"{formatted_errors}",
        "errors": errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = get_object_or_404(CustomUser, email=email)
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    reset_link = f"{settings.BASE_URL}{reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})}"
    
    try:
        send_mail(
            'Password Reset',
            f'Use the link below to reset your password:\n{reset_link}',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return Response({'message': 'Password reset link has been sent to your email'}, status=status.HTTP_200_OK)
    except Exception as e:
        print(f'Error sending email: {e}')
        return Response({'error': 'An error occurred while sending the email'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uid = request.query_params.get('uid')
    token = request.query_params.get('token')
    new_password = request.data.get('new_password')
    
    if not uid or not token or not new_password:
        return Response({'error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        uid = force_str(urlsafe_base64_decode(uid))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        user.password = make_password(new_password)
        user.save()
        return Response({'message': 'Password has been reset successfully'}, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid token or user'}, status=status.HTTP_400_BAD_REQUEST)

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'templates/password_reset_complete.html'
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'templates/password_reset_done.html'

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'error': 'Old password and new password are required'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user

    if not user.check_password(old_password):
        return Response({'error': 'Old password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

    user.password = make_password(new_password)
    user.save()

    return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)



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
        data_collection = DataCollection.objects.get(patient_id=id)

        week_data = {
            'mon': getattr(data_collection, 'mon', 0),
            'tues': getattr(data_collection, 'tues', 0),
            'wed': getattr(data_collection, 'wed', 0),
            'thur': getattr(data_collection, 'thur', 0),
            'fri': getattr(data_collection, 'fri', 0),
            'sat': getattr(data_collection, 'sat', 0),
            'sun': getattr(data_collection, 'sun', 0),
            'week': getattr(data_collection, 'week', 0),
            'all_time': getattr(data_collection, 'all_time', 0),
        }

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
            return Response({'message': 'No subcategories found for this category.'}, status=status.HTTP_204_NO_CONTENT)

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
            category=category, subcategory=subcategory, 
        ).values('id', 'title', 'url', 'category', 'subcategory', 'description')
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
    
    data_collection = DataCollection.objects.get(patient=user)
    week_data = {
        'mon': getattr(data_collection, 'mon', 0),
        'tues': getattr(data_collection, 'tues', 0),
        'wed': getattr(data_collection, 'wed', 0),
        'thur': getattr(data_collection, 'thur', 0),
        'fri': getattr(data_collection, 'fri', 0),
        'sat': getattr(data_collection, 'sat', 0),
        'sun': getattr(data_collection, 'sun', 0),
        'week': getattr(data_collection, 'week', 0),
        'all_time': getattr(data_collection, 'all_time', 0),
    }

    return Response({
        'generalVideos': general_videos or [], 
        'tasks': tasks or [], 
        'quote': quote or [], 
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
        videos = ModulesList.objects.filter(category=category, subcategory=subcategory, hospital=hospital).order_by('?')
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
            video_tracker.isCompleted = is_completed
            video_tracker.save()

            # Log watched data if completed
            if is_completed:
                WatchedData.objects.create(user=user, video=video_tracker.video, date=timezone.now().date())

                # Update patient’s data collection statistics
                current_date = timezone.now().date()
                current_day = current_date.strftime('%A')

                day_mapping = {
                    'Monday': 'mon',
                    'Tuesday': 'tues',
                    'Wednesday': 'wed',
                    'Thursday': 'thur',
                    'Friday': 'fri',
                    'Saturday': 'sat',
                    'Sunday': 'sun'
                }

                if current_day in day_mapping:
                    field_name = day_mapping[current_day]

                    data_collection, _ = DataCollection.objects.get_or_create(patient=user)

                    # Update relevant fields
                    setattr(data_collection, field_name, getattr(data_collection, field_name, 0) + 1)
                    data_collection.week = getattr(data_collection, 'week', 0) + 1
                    data_collection.all_time = getattr(data_collection, 'all_time', 0) + 1
                    data_collection.save()

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
def save_push_token(request):
    """Save or update the Expo push token for a user."""
    user = request.user
    token = request.data.get('pushToken')

    print(f"📩 Received push token for user {user.username}: {token}")

    if not token:
        print("❌ Error: No push token received")
        return Response({'error': 'Push token is required'}, status=400)

    # Save or update the push token for the user
    PushNotificationToken.objects.update_or_create(user=user, defaults={'token': token})

    print("✅ Token saved successfully")
    return Response({'message': 'Push token saved successfully'}, status=200)


