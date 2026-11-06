from django.urls import path

from . import views
from . import api
from . import admin_views

urlpatterns = [
    path('api/v1/fishing-zones/', admin_views.mobile_zones),
    path('api/v1/fishing-zones/<uuid:zone_id>/', admin_views.mobile_zones),
    path('api/v1/admin/users/', admin_views.mobile_users),
    path('api/v1/admin/overview/', admin_views.mobile_overview),
    path('api/v1/admin/devices/', admin_views.mobile_devices),
    path('api/v1/admin/devices/<int:device_id>/history/', admin_views.mobile_device_history),
    path('fishing-zones/', admin_views.browser_zones, name='fishing_zones'),
    path('fishing-zones/<uuid:zone_id>/', admin_views.browser_zones),
    path('users/', admin_views.users_page, name='users'),
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
    path('alerts/feed/', views.alerts_feed, name='alerts_feed'),
    path('alerts/<int:alert_id>/dismiss/', views.dismiss_alert_view, name='dismiss_alert'),
    path('reports/', views.reports, name='reports'),
    path('profile/', views.profile, name='profile'),
    path('map/', views.map_view, name='map'),
    path('settings/', views.settings_view, name='settings'),
]
