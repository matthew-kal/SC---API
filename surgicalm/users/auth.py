from django.conf import settings
from django.contrib.auth import authenticate

def auth_dev(key):
    return key == settings.DEV_KEY

def auth_nurse(username, password, request=None):
    user = authenticate(request=request, username=username, password=password)
    if user and user.user_type == 'nurse':
        return user
    return None

def auth_patient(username, password, request=None):
    user = authenticate(request=request, username=username, password=password)
    if user and user.user_type == 'patient':
        return user
    return None