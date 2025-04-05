from django.contrib import admin

# users/admin.py
from django.contrib.auth.admin import UserAdmin
from .models import *

admin.site.register(CustomUser, UserAdmin)
