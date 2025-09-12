# surgicalm/users/auth_decorators.py

from functools import wraps
from django.conf import settings
from django.http import JsonResponse
from google.oauth2 import id_token
from google.auth.transport import requests

def oidc_auth_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        
        auth_header = request.headers.get('Authorization')
        logger.info(f"[OIDC_DEBUG] Authorization header present: {bool(auth_header)}")

        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning("[OIDC_DEBUG] Missing or invalid Authorization header")
            return JsonResponse({'error': 'Authorization header is missing or invalid.'}, status=401)

        token = auth_header.split(' ')[1]
        logger.info(f"[OIDC_DEBUG] Token length: {len(token)}")

        try:
            logger.info(f"[OIDC_DEBUG] Verifying token with audience: {settings.BASE_URL}")
            
            # Try multiple audiences that might be valid
            valid_audiences = [
                settings.BASE_URL,  # https://api.surgicalm.com
                "https://api.surgicalm.com",  # Explicit
                "api.surgicalm.com",  # Without https
                settings.CLOUD_RUN_URL,  # Cloud Run URL for scheduler
            ]
            # Filter out empty values
            valid_audiences = [aud for aud in valid_audiences if aud]
            
            id_info = None
            for audience in valid_audiences:
                try:
                    logger.info(f"[OIDC_DEBUG] Trying audience: {audience}")
                    id_info = id_token.verify_oauth2_token(
                        token, 
                        requests.Request(), 
                        audience=audience
                    )
                    logger.info(f"[OIDC_DEBUG] Token verified successfully with audience: {audience}")
                    break
                except ValueError as e:
                    logger.warning(f"[OIDC_DEBUG] Failed with audience {audience}: {e}")
                    continue
            
            if not id_info:
                logger.error("[OIDC_DEBUG] Token verification failed with all audiences")
                return JsonResponse({'error': 'Invalid token: audience mismatch'}, status=401)
            
            logger.info(f"[OIDC_DEBUG] Token verified successfully. Email: {id_info.get('email')}")
            logger.info(f"[OIDC_DEBUG] Token details: {id_info}")

            if id_info.get('email') != settings.SERVICE_ACCOUNT_EMAIL:
                logger.warning(f"[OIDC_DEBUG] Service account mismatch. Expected: {settings.SERVICE_ACCOUNT_EMAIL}, Got: {id_info.get('email')}")
                return JsonResponse({'error': 'Token service account mismatch.'}, status=403)

            logger.info("[OIDC_DEBUG] Authentication successful")
        except Exception as e:
            logger.error(f"[OIDC_DEBUG] Token verification failed: {e}")
            return JsonResponse({'error': f'Invalid token: {e}'}, status=401)

        return view_func(request, *args, **kwargs)

    return _wrapped_view