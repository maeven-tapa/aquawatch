"""Mobile JSON API. Browser pages retain their existing session/CSRF handling."""
import hashlib
import json
import math
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import wraps

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Alert, Device, DeviceReading, MobileAuthWindow, MobileToken, MonitoringArea, Report, SignupChallenge, SyncReceipt, UserProfile


class ApiError(Exception):
    def __init__(self, message, status=400, event_id=None):
        self.message, self.status, self.event_id = message, status, event_id


def secret(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ApiError(f'Invalid {key}.')
    return value


def text(data, key, limit=128, required=False, default=''):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ApiError(f'Invalid {key}.')
    return value.strip()


def boolean(data, key, default=False):
    value = data.get(key, default)
    if type(value) is not bool:
        raise ApiError(f'{key} must be true or false.')
    return value


def coordinate(data, key, bound):
    value = data.get(key)
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > bound:
        raise ApiError(f'Invalid {key}.')
    return value


def timestamp(data, key):
    value = data.get(key)
    if type(value) is not int:
        raise ApiError(f'{key} must be Unix milliseconds.')
    try:
        result = datetime.fromtimestamp(value / 1000, dt_timezone.utc)
    except (ValueError, OverflowError, OSError):
        raise ApiError(f'Invalid {key}.')
    if result.year < 2000 or result > timezone.now() + timedelta(minutes=5):
        raise ApiError(f'Invalid {key}.')
    return result


def api(methods, protected=True):
    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request):
            try:
                if request.method not in methods:
                    raise ApiError('Method not allowed.', 405)
                if protected:
                    authorization = request.headers.get('Authorization', '')
                    if not authorization.startswith('Bearer '):
                        raise ApiError('Sign in to AquaWatch Web.', 401)
                    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
                    token = MobileToken.objects.select_related('user').filter(digest=digest).first()
                    if (not token or token.expires_at <= timezone.now() or not token.user.is_active
                            or token.password_signature != token.user.get_session_auth_hash()):
                        raise ApiError('Your session expired. Sign in again.', 401)
                    request.mobile_token = token
                    request.mobile_user = token.user
                data = {}
                if request.method == 'POST':
                    if request.content_type != 'application/json':
                        raise ApiError('Send application/json.', 415)
                    if len(request.body) > 512_000:
                        raise ApiError('Request too large.', 413)
                    try:
                        data = json.loads(request.body)
                    except (ValueError, UnicodeDecodeError):
                        raise ApiError('Invalid JSON.')
                    if not isinstance(data, dict):
                        raise ApiError('Send a JSON object.')
                response = JsonResponse(view(request, data))
            except ApiError as error:
                body = {'error': error.message}
                if error.event_id:
                    body['failed_event_id'] = error.event_id
                response = JsonResponse(body, status=error.status)
            except ValidationError as error:
                response = JsonResponse({'error': ' '.join(error.messages)}, status=400)
            except IntegrityError:
                response = JsonResponse({'error': 'This record conflicts with an existing record.'}, status=409)
            response['Cache-Control'] = 'no-store'
            return response
        return wrapper
    return decorate


def issue_token(user):
    raw = secrets.token_urlsafe(48)
    expires = timezone.now() + timedelta(days=30)
    MobileToken.objects.filter(user=user, expires_at__lte=timezone.now()).delete()
    MobileToken.objects.create(digest=hashlib.sha256(raw.encode()).hexdigest(), user=user,
                               password_signature=user.get_session_auth_hash(), expires_at=expires)
    return {'token': raw, 'expires_at': expires.isoformat(), 'snapshot': snapshot(user)}


def throttle(request, identity):
    now = timezone.now()
    bucket = int(now.timestamp()) // 300
    key = hashlib.sha256((request.META.get('REMOTE_ADDR', '') + identity + str(bucket)).encode()).hexdigest()
    MobileAuthWindow.objects.filter(expires_at__lt=now).delete()
    window, _ = MobileAuthWindow.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(minutes=5)})
    MobileAuthWindow.objects.filter(pk=key).update(attempts=F('attempts') + 1)
    window.refresh_from_db()
    if window.attempts > 15:
        raise ApiError('Too many attempts. Try again in five minutes.', 429)


@api(['GET'], protected=False)
def health(request, data):
    return {'service': 'aquawatch', 'api_version': 1}


@api(['POST'], protected=False)
def login(request, data):
    identifier = text(data, 'email', 254, required=True)
    throttle(request, identifier.lower())
    username = identifier
    if '@' in identifier:
        matches = list(User.objects.filter(email__iexact=identifier)[:2])
        if len(matches) != 1:
            raise ApiError('Invalid account or password. Use your web username if the email is shared.', 401)
        username = matches[0].username
    user = authenticate(request, username=username, password=secret(data, 'password'))
    if user is None:
        raise ApiError('Invalid account or password.', 401)
    return issue_token(user)


@api(['POST'], protected=False)
def request_signup_code(request, data):
    email = text(data, 'email', 150, required=True).lower()
    validate_email(email)
    throttle(request, email)
    if User.objects.filter(email__iexact=email).exists():
        raise ApiError('This account already exists. Sign in instead.', 409)
    if settings.EMAIL_BACKEND.endswith('smtp.EmailBackend') and not settings.EMAIL_HOST:
        raise ApiError('Email verification is not configured on the server. Contact AquaWatch support.', 503)
    existing = SignupChallenge.objects.filter(email=email).first()
    if existing and existing.expires_at > timezone.now() + timedelta(minutes=4, seconds=30):
        raise ApiError('Wait 30 seconds before requesting another code.', 429)
    code = str(secrets.randbelow(900_000) + 100_000)
    try:
        send_mail('Your AquaWatch verification code', f'Your AquaWatch code is {code}. It expires in five minutes.',
                  settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception:
        raise ApiError('Unable to send verification email. Please try again later.', 503)
    SignupChallenge.objects.update_or_create(email=email, defaults={
        'code_digest': make_password(code), 'expires_at': timezone.now() + timedelta(minutes=5), 'attempts': 0})
    return {'sent': True, 'expires_in': 300}


@api(['POST'], protected=False)
def register(request, data):
    email = text(data, 'email', 150, required=True).lower()
    validate_email(email)
    throttle(request, email)
    if not boolean(data, 'accepted_terms'):
        raise ApiError('Accept the Terms and Conditions.')
    if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username=email).exists():
        raise ApiError('This account already exists. Sign in using your web password.', 409)
    user = User(username=email, email=email, first_name=text(data, 'first_name', 150),
                last_name=text(data, 'last_name', 150))
    password = secret(data, 'password')
    validate_password(password, user=user)
    user.set_password(password)
    with transaction.atomic():
        challenge = SignupChallenge.objects.select_for_update().filter(email=email).first()
        if not challenge or challenge.expires_at <= timezone.now() or challenge.attempts >= 5:
            raise ApiError('Your code expired. Request a new code.')
        code_matches = check_password(text(data, 'code', 6, required=True), challenge.code_digest)
        if not code_matches:
            challenge.attempts += 1
            challenge.save(update_fields=['attempts'])
    if not code_matches:
        raise ApiError('That verification code does not match.')
    try:
        with transaction.atomic():
            challenge = SignupChallenge.objects.select_for_update().filter(email=email).first()
            if (not challenge or challenge.expires_at <= timezone.now() or challenge.attempts >= 5
                    or not check_password(data['code'], challenge.code_digest)):
                raise ApiError('Request a new verification code.')
            user.save()
            UserProfile.objects.create(user=user, role=text(data, 'role', default='Coastal responder'),
                                       station=text(data, 'station'), phone=text(data, 'phone', 64))
            MonitoringArea.objects.create(user=user)
            challenge.delete()
    except IntegrityError:
        raise ApiError('This account already exists. Sign in instead.', 409)
    return issue_token(user)


@api(['POST'])
def logout(request, data):
    request.mobile_token.delete()
    return {'logged_out': True}


@api(['POST'])
def change_password(request, data):
    user = request.mobile_user
    if not user.check_password(secret(data, 'current_password')):
        raise ApiError('Current password is incorrect.')
    password = secret(data, 'new_password')
    validate_password(password, user=user)
    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=['password'])
        MobileToken.objects.filter(user=user).delete()
        return issue_token(user)


def snapshot(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    area, _ = MonitoringArea.objects.get_or_create(user=user)
    devices = []
    Device.objects.filter(user=user, last_status_at__lt=timezone.now() - timedelta(minutes=10), status='Active').update(status='Offline')
    for device in Device.objects.filter(user=user):
        reading = device.readings.order_by('-received_at', '-id').first()
        devices.append({
            'id': device.mobile_id or f'web-{device.pk}', 'server_id': device.pk,
            'name': device.name, 'type': device.device_type, 'serial': device.serial, 'imei': device.imei,
            'sim': device.sim, 'owner': device.owner, 'driver': device.driver, 'vessel': device.vessel,
            'reg': device.registration, 'contact': device.contact,
            'status': device.status, 'lastLocation': device.last_location, 'lastUpdated': device.last_updated,
            'lastStatusAt': int(device.last_status_at.timestamp() * 1000) if device.last_status_at else 0,
            'photoLabel': device.photo.url if device.photo else '',
            'waterLevel': (reading.water_level_value or '-- cm') if reading else '-- cm',
            'gyro': f'{reading.gyro_x} / {reading.gyro_y} deg' if reading else 'Not reported',
            'gsm': reading.gsm_signal if reading else 'Not reported',
            'gpsLocation': f'{reading.latitude}, {reading.longitude}' if reading else device.last_location,
            'acceleration': reading.acceleration if reading else 'Not reported',
            'capabilities': {'water_level': device.water_level, 'gyro': device.gyro, 'gsm': device.gsm, 'gps': device.gps},
        })
    return {
        'user': {'id': user.pk, 'username': user.username, 'email': user.email, 'first_name': user.first_name,
                 'last_name': user.last_name, 'phone': profile.phone, 'role': profile.role, 'station': profile.station},
        'area': {'latitude': area.latitude, 'longitude': area.longitude, 'label': area.label},
        'devices': devices,
        'reports': [{'id': report.mobile_id or f'web-{report.pk}', 'type': report.type, 'location': report.location,
                     'severity': report.severity, 'time': report.time, 'description': report.description}
                    for report in Report.objects.filter(user=user).order_by('id')],
        'alerts': [{'id': alert.source_id or f'web-{alert.pk}', 'type': alert.type, 'location': alert.location, 'time': alert.time,
                    'severity': alert.severity, 'description': alert.description}
                   for alert in Alert.objects.filter(user=user).order_by('-id')],
    }


def find_device(user, device_id):
    device = Device.objects.filter(user=user, mobile_id=device_id).first()
    if device is None and device_id.startswith('web-') and device_id[4:].isdigit():
        device = Device.objects.filter(user=user, pk=int(device_id[4:])).first()
    if device is None:
        raise ApiError('Register this device before uploading readings.')
    return device


def apply_event(user, kind, data):
    if kind == 'device.upsert':
        device_id = text(data, 'id', required=True)
        device = Device.objects.filter(user=user, mobile_id=device_id).first()
        if device is None and device_id.startswith('web-'):
            device = find_device(user, device_id)
        serial = text(data, 'serial', required=True)
        if device is None:
            matches = list(Device.objects.filter(user=user, serial=serial)[:2])
            if len(matches) > 1:
                raise ApiError('Duplicate serial numbers on your web account. Resolve them before linking.', 409)
            device = matches[0] if matches else Device(user=user)
        device.mobile_id = device_id
        for incoming, field in {'name': 'name', 'type': 'device_type', 'serial': 'serial', 'imei': 'imei',
                                'sim': 'sim', 'owner': 'owner', 'driver': 'driver', 'vessel': 'vessel',
                                'reg': 'registration', 'contact': 'contact'}.items():
            setattr(device, field, text(data, incoming, 64 if incoming == 'sim' else 128))
        device.save()
    elif kind == 'report.create':
        report_id = text(data, 'id', required=True)
        Report.objects.get_or_create(user=user, mobile_id=report_id, defaults={
            'type': text(data, 'type', required=True), 'location': text(data, 'location', required=True),
            'severity': text(data, 'severity', 64, required=True),
            'time': timestamp(data, 'created_at').strftime('%Y-%m-%d %H:%M:%S UTC'),
            'description': text(data, 'description', 20_000),
        })
    elif kind == 'reading.create':
        device = find_device(user, text(data, 'device_id', required=True))
        received = timestamp(data, 'received_at')
        reading = DeviceReading.objects.create(
            device=device, received_at=received, latitude=coordinate(data, 'latitude', 90),
            longitude=coordinate(data, 'longitude', 180), gyro_x=text(data, 'gyro_x', 64),
            gyro_y=text(data, 'gyro_y', 64), gsm_signal=text(data, 'gsm_signal'),
            acceleration=text(data, 'acceleration'), water_level_value=text(data, 'water_level_value'),
            is_distress=boolean(data, 'is_distress'), alert_type=text(data, 'alert_type'),
        )
        if not device.last_status_at or received >= device.last_status_at:
            device.last_status_at = received
            device.last_location = f'{reading.latitude}, {reading.longitude}'
            device.last_updated = received.strftime('%Y-%m-%d %H:%M:%S UTC')
            device.status = 'Active' if received >= timezone.now() - timedelta(minutes=10) else 'Offline'
            device.save(update_fields=['last_status_at', 'last_location', 'last_updated', 'status'])
        if reading.alert_type:
            Alert.objects.create(user=user, type=reading.alert_type, location=f'{reading.latitude}, {reading.longitude}',
                                 source_id=f'{data["device_id"]}-{data["received_at"]}',
                                 time=received.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                 severity='Critical' if reading.is_distress else 'High',
                                 description=f'{device.name} reported {reading.alert_type}.')
    elif kind == 'profile.update':
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for key in ('phone', 'role', 'station'):
            setattr(profile, key, text(data, key, 64 if key == 'phone' else 128))
        user.first_name = text(data, 'first_name', 150)
        user.last_name = text(data, 'last_name', 150)
        user.save(update_fields=['first_name', 'last_name'])
        profile.save()
    elif kind == 'area.update':
        area, _ = MonitoringArea.objects.get_or_create(user=user)
        area.latitude = coordinate(data, 'latitude', 90)
        area.longitude = coordinate(data, 'longitude', 180)
        area.label = text(data, 'label', required=True)
        area.save()
    else:
        raise ApiError('Unknown event kind.')


@api(['GET', 'POST'])
def sync(request, data):
    user = request.mobile_user
    events = data.get('events', [])
    if not isinstance(events, list) or len(events) > 100:
        raise ApiError('Send up to 100 events.')
    accepted = []
    with transaction.atomic():
        # Serialize all mobile writes for this user, including duplicate HTTP retries.
        User.objects.select_for_update().get(pk=user.pk)
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get('data'), dict):
                raise ApiError('Invalid event.')
            event_id = text(event, 'id', required=True)
            digest = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            try:
                receipt, created = SyncReceipt.objects.get_or_create(user=user, event_id=event_id,
                                                                   defaults={'payload_digest': digest})
                if receipt.payload_digest != digest:
                    raise ApiError('An event ID was reused with different data.', 409)
                if created:
                    apply_event(user, text(event, 'kind', required=True), event['data'])
            except ApiError as error:
                error.event_id = event_id
                raise
            except IntegrityError:
                raise ApiError('This record conflicts with an existing record.', 409, event_id)
            accepted.append(event_id)
        result = snapshot(user)
    return {'accepted': accepted, 'snapshot': result}
