from django.urls import path, reverse_lazy
from surgicalm.users.views import *
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [

    # AUTH #

    # Nurse Login
    path('nurse/login/', nurse_login, name='nurse_login'),
    # Patient Account Creation
    path('patient/register/', patient_register, name='patient_register'),
    # Patient Login
    path('patient/login/', patient_login, name='patient_login'),

    # Forgot Password
    path(
        "password-reset/",
        request_password_reset,
        name="request_password_reset",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="password_reset_form.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # JWT #
    
    # Token Creation 
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # Access Token Refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Logout
    path('logout/', logout, name='logout'),

    # ADMIN #

    # Nurse Account Creation
    path('dev/', create_nurse, name='create_nurse'),

    # NURSE #

    # Patient Search
    path('patients-list/', search_patients, name='search_patients'),
    path('patient-graph/<int:id>/', patient_graph, name='patient_graph'),

    # PATIENT #

    # Dashboard
    path('dashboard/', dashboard, name='dashboard'),
    # Assorted Modules
    path('categories/', category_list, name='category_list'),
    path('<int:category_id>/subcategories/', subcategory_list, name="subcategory_list"),
    path('<int:category>/<int:subcategory>/modules-list/', modules_list, name='modules_list'),
    # Settings
    path('user-settings/', user_settings, name='user_settings'),
    path('change-password/', change_password, name='change_password'),
    path('delete-account/', delete_account, name='delete_account'),
    # Assignment Completion
    path('update_video_completion/<int:videoId>/', update_video_completion, name='update_video_completion'),
    path('tasks/update-completion/<int:taskId>/', update_task_completion, name='update_task_completion'),
    # Notifications
    path('api/save-token/', save_push_token, name='save_push_token'),

    # Task Refresh
    path('tasks/refresh-all-user-data/', trigger_daily_user_refresh, name='trigger_daily_refresh'),

]