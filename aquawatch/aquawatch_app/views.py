import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import HttpResponseRedirect, get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    AccountForm,
    AlertForm,
    DeviceForm,
    MonitoringAreaForm,
    ProfileDetailsForm,
    ReportForm,
    SettingsForm,
    UserRegistrationForm,
)
from .models import Alert, Device, MonitoringArea, Report, UserProfile


def get_or_create_profile(user: User) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def get_or_create_monitoring_area(user: User) -> MonitoringArea:
    area, _ = MonitoringArea.objects.get_or_create(user=user)
    return area


def fetch_weather(latitude: float, longitude: float) -> dict:
    api_key = settings.OPENWEATHER_API_KEY.strip()
    if not api_key:
        return {
            'location': 'Quiapo District Coast Watch',
            'current': {'temperature': 27, 'description': 'Partly cloudy', 'icon': '02d'},
            'wind_speed': 12,
            'wind_gust': 16,
            'humidity': 78,
            'visibility': 8000,
            'forecast': [],
        }

    query = urlencode({
        'lat': latitude,
        'lon': longitude,
        'appid': api_key,
        'units': 'metric',
    })
    url = f'https://api.openweathermap.org/data/2.5/weather?{query}'
    request = Request(url, headers={'User-Agent': 'AquaWatch Web'})

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except (HTTPError, URLError, ValueError):
        return {
            'location': 'Quiapo District Coast Watch',
            'current': {'temperature': 27, 'description': 'Partly cloudy', 'icon': '02d'},
            'wind_speed': 12,
            'wind_gust': 16,
            'humidity': 78,
            'visibility': 8000,
            'forecast': [],
        }

    main = payload.get('main', {})
    wind = payload.get('wind', {})
    weather = (payload.get('weather') or [{}])[0]

    forecast = []
    try:
        forecast_query = urlencode({
            'lat': latitude,
            'lon': longitude,
            'appid': api_key,
            'units': 'metric',
        })
        forecast_url = f'https://api.openweathermap.org/data/2.5/forecast?{forecast_query}'
        forecast_request = Request(forecast_url, headers={'User-Agent': 'AquaWatch Web'})
        with urlopen(forecast_request, timeout=10) as forecast_response:
            forecast_payload = json.load(forecast_response)
        forecast_items = forecast_payload.get('list', [])
        seen_days = set()
        for item in forecast_items:
            timestamp = item.get('dt_txt', '')
            if not timestamp or '12:00:00' not in timestamp:
                continue
            date_label = timestamp.split(' ')[0]
            if date_label in seen_days:
                continue
            item_main = item.get('main', {})
            item_weather = (item.get('weather') or [{}])[0]
            forecast.append({
                'date': date_label,
                'temperature': int(item_main.get('temp', 0)),
                'description': item_weather.get('main', 'Marine'),
                'icon': item_weather.get('icon', '02d'),
            })
            seen_days.add(date_label)
            if len(forecast) >= 5:
                break
    except Exception:
        forecast = []

    return {
        'location': payload.get('name', 'Monitoring area'),
        'current': {
            'temperature': int(main.get('temp', 0)),
            'description': weather.get('description', 'Unknown').title(),
            'icon': weather.get('icon', '02d'),
        },
        'wind_speed': float(wind.get('speed', 0)),
        'wind_gust': float(wind.get('gust', wind.get('speed', 0))),
        'humidity': int(main.get('humidity', 0)),
        'visibility': int(payload.get('visibility', 0)),
        'forecast': forecast,
    }


def welcome(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'aquawatch_app/welcome.html')


def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm(request)

    return render(request, 'aquawatch_app/login.html', {'form': form})


def forgot_password(request):
    submitted = False
    if request.method == 'POST':
        submitted = True
    return render(request, 'aquawatch_app/forgot_password.html', {'submitted': submitted})


def terms(request):
    return render(request, 'aquawatch_app/terms.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            if User.objects.filter(username=username).exists():
                form.add_error('username', 'A user with that username already exists.')
            else:
                try:
                    user = form.save()
                except Exception as e:
                    form.add_error(None, 'Unable to create account. Please try a different username.')
                    user = None
            if not form.errors and user:
                user.first_name = form.cleaned_data.get('first_name', '')
                user.last_name = form.cleaned_data.get('last_name', '')
                user.email = form.cleaned_data.get('email', '')
                user.save()
                profile = get_or_create_profile(user)
                profile.role = form.cleaned_data.get('role', profile.role)
                profile.station = form.cleaned_data.get('station', profile.station)
                profile.phone = form.cleaned_data.get('phone', profile.phone)
                profile.save()
                MonitoringArea.objects.get_or_create(user=user)
                Alert.objects.get_or_create(
                    user=user,
                    type='Coastal security',
                    location='Manila Bay',
                    time='08:15',
                    severity='Medium',
                    defaults={'description': 'Create your first alert to keep the team informed.'},
                )
                login(request, user)
                return redirect('location')
    else:
        form = UserRegistrationForm()

    return render(request, 'aquawatch_app/register.html', {'form': form})


@login_required
def dashboard(request):
    user = request.user
    profile = get_or_create_profile(user)
    area = get_or_create_monitoring_area(user)
    weather_status = 'Updating live conditions'
    weather = fetch_weather(area.latitude, area.longitude)

    if weather.get('location') == 'Monitoring area':
        weather_status = 'Live weather unavailable'
    else:
        weather_status = f'{area.label} - Live weather: {weather.get("location")} '

    alerts = Alert.objects.filter(user=user).order_by('-id')[:5]
    devices = Device.objects.filter(user=user).order_by('-id')[:5]
    alert_count = Alert.objects.filter(user=user).count()
    device_count = Device.objects.filter(user=user).count()

    wind_speed = float(weather.get('wind_speed', 0))
    visibility = int(weather.get('visibility', 0))
    if wind_speed <= 10 and visibility >= 5000:
        condition_status = 'Safe to sail'
        condition_detail = 'Wind and visibility are within normal coastal operating ranges.'
        condition_level = 'safe'
    elif wind_speed <= 15 and visibility >= 3000:
        condition_status = 'Use caution'
        condition_detail = 'Conditions are changing. Monitor wind and visibility before departure.'
        condition_level = 'caution'
    else:
        condition_status = 'Unsafe conditions'
        condition_detail = 'Strong wind or low visibility may make coastal travel hazardous.'
        condition_level = 'danger'

    return render(
        request,
        'aquawatch_app/dashboard.html',
        {
            'profile': profile,
            'area': area,
            'weather': weather,
            'weather_status': weather_status,
            'alerts': alerts,
            'devices': devices,
            'alert_count': alert_count,
            'device_count': device_count,
            'visibility_km': visibility / 1000,
            'condition_status': condition_status,
            'condition_detail': condition_detail,
            'condition_level': condition_level,
        },
    )


@login_required
def location(request):
    area = get_or_create_monitoring_area(request.user)
    if request.method == 'POST':
        form = MonitoringAreaForm(request.POST, instance=area)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = MonitoringAreaForm(instance=area)

    return render(request, 'aquawatch_app/location.html', {
        'form': form,
        'area': area,
        'google_maps_key': settings.GOOGLE_MAPS_API_KEY,
    })


@login_required
def devices(request):
    user = request.user
    items = Device.objects.filter(user=user).order_by('-id')
    return render(request, 'aquawatch_app/devices.html', {'devices': items})


@login_required
def add_device(request):
    if request.method == 'POST':
        form = DeviceForm(request.POST, request.FILES)
        if form.is_valid():
            device = form.save(commit=False)
            device.user = request.user
            device.save()
            return redirect('devices')
    else:
        form = DeviceForm()
    return render(request, 'aquawatch_app/add_device.html', {'form': form})


@login_required
def device_detail(request, device_id):
    device = get_object_or_404(Device, id=device_id, user=request.user)
    return render(request, 'aquawatch_app/device_detail.html', {'device': device})


@login_required
def alerts(request):
    user = request.user
    items = Alert.objects.filter(user=user).order_by('-id')
    return render(request, 'aquawatch_app/alerts.html', {'alerts': items})


@login_required
def reports(request):
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.time = 'Now'
            report.save()
            messages.success(request, 'Incident report submitted.')
            return redirect('reports')
    else:
        form = ReportForm()
    items = Report.objects.filter(user=request.user).order_by('-id')
    return render(request, 'aquawatch_app/reports.html', {'form': form, 'reports': items})


@login_required
def profile(request):
    profile_record = get_or_create_profile(request.user)
    account_form = AccountForm(instance=request.user)
    details_form = ProfileDetailsForm(instance=profile_record)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            account_form = AccountForm(request.POST, instance=request.user)
            details_form = ProfileDetailsForm(request.POST, request.FILES, instance=profile_record)
            if account_form.is_valid() and details_form.is_valid():
                account_form.save()
                details_form.save()
                messages.success(request, 'Profile saved.')
                return redirect('profile')
        elif action == 'password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                login(request, user)
                messages.success(request, 'Password updated.')
                return redirect('profile')

    return render(request, 'aquawatch_app/profile.html', {
        'profile': profile_record,
        'account_form': account_form,
        'details_form': details_form,
        'password_form': password_form,
    })


@login_required
def settings_view(request):
    profile = get_or_create_profile(request.user)
    if request.method == 'POST':
        form = SettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved.')
            return redirect('settings')
    else:
        form = SettingsForm(instance=profile)

    return render(request, 'aquawatch_app/settings.html', {'form': form, 'profile': profile})


@login_required
def user_logout(request):
    logout(request)
    return redirect('welcome')


@login_required
def map_view(request):
    area = get_or_create_monitoring_area(request.user)
    profile = get_or_create_profile(request.user)
    return render(request, 'aquawatch_app/map.html', {
        'area': area,
        'profile': profile,
        'device_count': Device.objects.filter(user=request.user, status__iexact='Active').count(),
        'google_maps_key': settings.GOOGLE_MAPS_API_KEY,
    })
