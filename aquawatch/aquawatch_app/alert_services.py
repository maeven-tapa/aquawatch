from django.db.models import Q
from .models import Alert,AlertDismissal

def alert_key(alert):
    return alert.source_id or f'web-{alert.pk}'

def active_alerts(user=None):
    items=Alert.objects.all() if user is None else Alert.objects.filter(user=user)
    # Correlated existence avoids a client-side list and keeps source keys owner-scoped.
    from django.db.models import Exists,OuterRef,Value,CharField
    from django.db.models.functions import Cast,Concat
    dismissed=AlertDismissal.objects.filter(user_id=OuterRef('user_id')).filter(
        Q(alert_key=OuterRef('source_id')) | Q(alert_key=Concat(Value('web-'),Cast(OuterRef('pk'),output_field=CharField()))))
    return items.annotate(is_dismissed=Exists(dismissed)).filter(is_dismissed=False)

def dismiss_alert(alert):
    AlertDismissal.objects.get_or_create(user=alert.user,alert_key=alert_key(alert))

def serialize_alert(alert):
    coordinates=alert.location.split(',')
    try:
        lat,lng=map(float,coordinates)
        if not (-90<=lat<=90 and -180<=lng<=180): raise ValueError()
    except (ValueError,TypeError):lat=lng=None
    return {'id':alert_key(alert),'server_id':alert.pk,'type':alert.type,'location':alert.location,
            'time':alert.time,'severity':alert.severity,'description':alert.description,
            'latitude':lat,'longitude':lng,'device_name':alert.device.name if alert.device else ''}

def record_device_alert(user,device,source_id,received,latitude,longitude,kind,distress):
    # Sync serializes writes per account. Backfill and live-reading events share a
    # source identity, so receipt retries and historical uploads cannot duplicate it.
    existing=Alert.objects.filter(user=user,source_id=source_id).first()
    if existing:
        if existing.device_id is None:
            existing.device=device;existing.save(update_fields=['device'])
        return existing
    return Alert.objects.create(user=user,device=device,source_id=source_id,type=kind,
        location=f'{latitude}, {longitude}',time=received.strftime('%Y-%m-%d %H:%M:%S UTC'),
        severity='Critical' if distress else 'High',description=f'{device.name} reported {kind}.')
