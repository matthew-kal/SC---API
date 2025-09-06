
import logging
import time 

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
from datetime import timedelta

from google.cloud import storage
from google.auth import impersonated_credentials
from google.auth import default
            

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from axes.decorators import axes_dispatch
from django_ratelimit.decorators import ratelimit
from django_ratelimit.core import is_ratelimited

from surgicalm.users.models import *  
from surgicalm.users.auth import *
from surgicalm.users.serializers import *
from .services import calculate_weekly_watched_data, refresh_user_data

logger = logging.getLogger(__name__)

User = get_user_model()

# ADMIN FUNCTIONS

@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='5/h', method='POST', block=True)
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

@permission_classes([AllowAny])
@api_view(['GET'])
def health_check(request):
    return Response({"status": "healthy"}, status=status.HTTP_200_OK)

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
        patient = serializer.save()                    
        logger.info("Nurse %s created patient %s", request.user.id, patient.id)

        # Assign initial modules, tasks, and quotes to the new patient
        try:
            refresh_user_data(patient)
            logger.info("Successfully assigned initial content to patient %s", patient.id)
        except Exception as e:
            logger.error(f"Failed to assign initial content to patient {patient.id}: {e}")
            # Don't fail the registration if content assignment fails
            # The patient can still be created and content will be assigned during daily refresh

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
    search_query = request.GET.get('query', '').strip()
    # Default to 'text' search if searchBy is not provided
    search_by = request.GET.get('searchBy', 'text') 
    hospital = request.user.hospital

    if not search_query:
        return Response([], status=status.HTTP_200_OK)

    # Base queryset for patients in the nurse's hospital
    base_queryset = CustomUser.objects.filter(user_type='patient', hospital=hospital)

    patients = CustomUser.objects.none() # Start with an empty queryset

    if search_by == 'id':
        try:
            # Perform a direct, fast lookup by primary key (ID)
            patient_id = int(search_query)
            patients = base_queryset.filter(id=patient_id)
        except (ValueError, TypeError):
            # If the query is not a valid integer, return an error
            return Response({"error": "Invalid ID format."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        # Default to FULLTEXT search for 'text', 'username', 'email', etc.
        # We add a '+' to each word to make it a boolean search for all terms.
        terms = [f'+{term}' for term in search_query.split()]
        if terms:
            terms[-1] += '*'  # Add the wildcard to the last term
        boolean_search_query = ' '.join(terms)

        patients = base_queryset.extra(
            where=["MATCH(username, email) AGAINST(%s IN BOOLEAN MODE)"],
            params=[boolean_search_query]
        )

    if not patients.exists():
        # Return an empty list with a 200 OK status for "no results found"
        return Response([], status=status.HTTP_200_OK)

    serializer = UserSerializer(patients, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_graph(request, id):
    try:
        # Ensure the requesting nurse can only see patients in their own hospital
        patient = CustomUser.objects.get(id=id, hospital=request.user.hospital)
        week_data = calculate_weekly_watched_data(patient)
        return Response({'weekData': week_data}, status=status.HTTP_200_OK)
    except CustomUser.DoesNotExist:
        return Response({'error': 'Patient not found for this hospital.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error generating patient graph for user {id}: {e}")
        return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    

# PATIENT

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def category_list(request):
    """Returns all categories, their IDs, and icons for the requester's hospital."""
    user_hospital = request.user.hospital
    if user_hospital is None:
        return Response({"error": "User is not associated with any hospital."}, status=status.HTTP_400_BAD_REQUEST)
    
    categories = ModuleCategories.objects.filter(hospital=user_hospital)
    serializer = ModuleCategorySerializer(categories, many=True)
    return Response({"categories": serializer.data}, status=status.HTTP_200_OK)

    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subcategory_list(request, category_id):
    """Returns all subcategory names for a given category ID."""
    try:
        hospital = request.user.hospital

        if not ModuleCategories.objects.filter(id=category_id, hospital_id=hospital).exists():
            return Response({'error': 'Category not found for this hospital.'}, status=status.HTTP_404_NOT_FOUND)

        subcategories = ModuleSubcategories.objects.filter(category_id=category_id, hospital_id=hospital)
        
        if not subcategories.exists():
            return Response({"subcategories": []}, status=status.HTTP_200_OK)

        serializer = ModuleSubcategorySerializer(subcategories, many=True)
        return Response({"subcategories": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"An unexpected error occurred in subcategory_list: {str(e)}")
        return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def modules_list(request, category, subcategory):

    try:
        # Ensure only modules from the user's hospital are accessible
        videos = ModulesList.objects.filter(
            category_id=category, subcategory_id=subcategory, hospital=request.user.hospital
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
def get_module_signed_url(request, module_id):
    """
    Generates a short-lived, secure signed URL for a given module.
    Only accessible to users within the same hospital as the module.
    """
    logger.info(f"[SIGNED_URL] Request received for module {module_id} by user {request.user.id} "
                f"(hospital={getattr(request.user, 'hospital', None)})")

    try:
        # STEP 1: Verify module belongs to the user’s hospital
        logger.debug(f"[SIGNED_URL] Attempting to fetch module {module_id}...")
        module = ModulesList.objects.get(id=module_id, hospital=request.user.hospital)
        logger.info(f"[SIGNED_URL] Found module {module_id} for hospital {request.user.hospital}")

        file_url = module.url
        logger.debug(f"[SIGNED_URL] Raw file_url from DB: {file_url}")

        # STEP 2: Derive the object path inside the bucket
        if file_url.startswith('gs://'):
            file_path_in_bucket = file_url.split('/', 3)[-1] if '/' in file_url else file_url
            logger.debug(f"[SIGNED_URL] Derived path from gs://: {file_path_in_bucket}")
        elif 'storage.googleapis.com' in file_url or 'storage.cloud.google.com' in file_url:
            url_parts = file_url.split('/')
            if len(url_parts) > 4:
                file_path_in_bucket = '/'.join(url_parts[4:])
            else:
                file_path_in_bucket = url_parts[-1]
            logger.debug(f"[SIGNED_URL] Derived path from https://storage.googleapis.com/: {file_path_in_bucket}")
        else:
            file_path_in_bucket = file_url.lstrip('/')
            logger.debug(f"[SIGNED_URL] Derived path (fallback): {file_path_in_bucket}")

        # STEP 3: Initialize storage client
        try:
            storage_client = storage.Client()
            logger.info("[SIGNED_URL] Initialized Google Cloud Storage client.")
        except Exception as client_err:
            logger.error(f"[SIGNED_URL] Failed to init GCS client: {client_err}", exc_info=True)
            return Response({"error": "Storage client initialization failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        bucket_name = settings.STORAGE_BUCKET_NAME
        logger.info(f"[SIGNED_URL] Using bucket: {bucket_name}, path: {file_path_in_bucket}")

        # STEP 4: Get blob reference
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path_in_bucket)
        logger.debug(f"[SIGNED_URL] Blob object created for {file_path_in_bucket}")

        # STEP 5: Generate signed URL using service account impersonation
        try:
            
            # Get default credentials (will be the Cloud Run service account)
            source_credentials, project_id = default()
            
            # Create impersonated credentials for signing
            # Note: We're impersonating the same service account to get signing capabilities
            target_credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=settings.SERVICE_ACCOUNT_EMAIL,
                target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            
            # Create a new storage client with the impersonated credentials
            signing_client = storage.Client(credentials=target_credentials)
            signing_bucket = signing_client.bucket(bucket_name)
            signing_blob = signing_bucket.blob(file_path_in_bucket)
            
            # Generate the signed URL
            signed_url = signing_blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=90),
                method="GET",
            )
            
            logger.info(f"[SIGNED_URL] Successfully generated signed URL for module {module_id}")
            return Response({"signedUrl": signed_url}, status=status.HTTP_200_OK)

        except Exception as gen_err:
            logger.error(f"[SIGNED_URL] Failed to generate signed URL for module {module_id}: {gen_err}", exc_info=True)
            return Response({"error": "Signed URL generation failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except ModulesList.DoesNotExist:
        logger.warning(f"[SIGNED_URL] Module {module_id} not found or not in hospital {request.user.hospital}")
        return Response({"error": "Module not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"[SIGNED_URL] Unexpected error for module {module_id}: {e}", exc_info=True)
        return Response({"error": "Could not generate media URL."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    user = request.user

    assigned_videos = AssignedModules.objects.filter(patient=user).select_related('video__category')
    assigned_tasks = AssignedTask.objects.filter(patient=user).select_related('task')
    assigned_quote = AssignedQuote.objects.filter(patient=user).select_related('quote').first()

    # Use the serializers created in the previous task
    video_serializer = AssignedModuleSerializer(assigned_videos, many=True)
    task_serializer = AssignedTaskSerializer(assigned_tasks, many=True)
    quote_serializer = AssignedQuoteSerializer(assigned_quote)

    # Call the reusable helper for graph data
    week_data = calculate_weekly_watched_data(user)

    return Response({
        'generalVideos': video_serializer.data,
        'tasks': task_serializer.data,
        'quote': quote_serializer.data if assigned_quote else None,
        'weekData': week_data,
    }, status=status.HTTP_200_OK)

  

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
        # Use the existing UserSerializer for a consistent data structure
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"An unexpected error occurred in user_settings: {str(e)}")
        return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

@api_view(['POST'])
@permission_classes([AllowAny]) # We use a secret key for auth, not user login
@axes_dispatch
def trigger_daily_user_refresh(request):
    """
    A secure endpoint for Cloud Scheduler to trigger the daily data refresh for all patients.
    """
    # 1. AUTHORIZATION: Check for the secret header from Cloud Scheduler
    auth_header = request.headers.get('X-Cron-Authorization')
    expected_secret = auth_cron(auth_header)

    if not expected_secret:
        logger.warning(f"Unauthorized attempt to access daily refresh endpoint.")
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        patients = User.objects.filter(user_type='patient')
        processed_count = 0
        for patient in patients:
            try:
                with transaction.atomic():
                    refresh_user_data(patient)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to refresh data for user {patient.id}: {e}")
        
        message = f"Successfully refreshed data for {processed_count} users."
        logger.info(message)
        return Response({"message": message}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"A critical error occurred during the daily refresh task: {e}")
        return Response({"error": "An internal error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

