from django.urls import path

from . import views
from . import api

urlpatterns = [
    path('api/v1/health/', api.health, name='api_health'),
    path('api/v1/auth/login/', api.login, name='api_login'),
    path('api/v1/auth/register/', api.register, name='api_register'),
    path('api/v1/auth/request-code/', api.request_signup_code, name='api_request_code'),
    path('api/v1/auth/logout/', api.logout, name='api_logout'),
    path('api/v1/auth/password/', api.change_password, name='api_password'),
    path('api/v1/sync/', api.sync, name='api_sync'),
    path('', views.welcome, name='welcome'),
    path('login/', views.user_login, name='login'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('terms/', views.terms, name='terms'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('location/', views.location, name='location'),
    path('devices/', views.devices, name='devices'),
    path('devices/add/', views.add_device, name='add_device'),
    path('devices/<int:device_id>/', views.device_detail, name='device_detail'),
    path('alerts/', views.alerts, name='alerts'),
    path('reports/', views.reports, name='reports'),
    path('profile/', views.profile, name='profile'),
    path('map/', views.map_view, name='map'),
    path('settings/', views.settings_view, name='settings'),
]
