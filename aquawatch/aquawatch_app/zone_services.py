from datetime import date
from calendar import monthrange
from uuid import UUID
from django.db import transaction
from django.db.models import Q
from .models import FishingZone
from .api import ApiError

def month_date(value):
    try:
        result=date.fromisoformat(str(value)+'-01')
        if len(value)!=7 or not 2000<=result.year<=2100: raise ValueError()
        return result
    except (ValueError,TypeError):
        raise ApiError('Use a calendar month in YYYY-MM format (2000–2100).')

def monthly_zones(user, period):
    items=FishingZone.objects.filter(date__month=period.month).filter(
        Q(date__year=period.year) | Q(repeats_annually=True,date__year__lt=period.year))
    if not (user.is_staff or user.is_superuser):
        items=items.filter(active=True)
    return items


def serialize_zone(zone, period=None):
    occurrence=zone.date
    if period is not None and zone.repeats_annually:
        occurrence=date(period.year,zone.date.month,min(zone.date.day,monthrange(period.year,zone.date.month)[1]))
    return {'id':str(zone.pk),'title':zone.title,'month':zone.date.strftime('%Y-%m'),
            'date':zone.date.isoformat(),
            'occurrence_date':occurrence.isoformat(),'repeats_annually':zone.repeats_annually,
            'published_at':zone.published_at.isoformat() if zone.published_at else None,
            'center':{'lat':zone.latitude,'lng':zone.longitude},'boundary':zone.boundary,
            'area_square_meters':zone.area_square_meters,'active':zone.active,
            'version':zone.version,'proposed':True,'updated_at':zone.updated_at.isoformat()}

def zones_result(user, method, month=None, data=None, zone_id=None):
    if method=='GET':
        period=month_date(month)
        return {'month':period.strftime('%Y-%m'),'zones':[serialize_zone(z,period) for z in monthly_zones(user,period)]}
    if not (user.is_staff or user.is_superuser):
        raise ApiError('Administrator access is required to edit fishing zones.',403)
    data=data or {}
    with transaction.atomic():
        if zone_id:
            try: identifier=UUID(str(zone_id))
            except ValueError: raise ApiError('Zone not found.',404)
            zone=FishingZone.objects.select_for_update().filter(pk=identifier).first()
            if zone is None: raise ApiError('Zone not found.',404)
            if type(data.get('version')) is not int or data['version']!=zone.version:
                raise ApiError('This zone was changed elsewhere. Reload before saving.',409)
        else: zone=FishingZone()
        title=data.get('title')
        if not isinstance(title,str) or not title.strip() or len(title)>128:
            raise ApiError('Enter a zone name of 1–128 characters.')
        center=data.get('center',{})
        if not isinstance(center,dict): raise ApiError('Enter valid center coordinates.')
        if 'repeats_annually' in data:
            if type(data['repeats_annually']) is not bool:
                raise ApiError('Repeat every year must be true or false.')
            zone.repeats_annually=data['repeats_annually']
        zone.title=title.strip()
        if 'date' in data:
            try:
                value = data['date']
                if not isinstance(value,str) or len(value)!=10: raise ValueError()
                zone.date=date.fromisoformat(value)
                if zone.date.isoformat()!=value: raise ValueError()
                if not 2000<=zone.date.year<=2100: raise ValueError()
            except (ValueError,TypeError):
                raise ApiError('Use an exact date in YYYY-MM-DD format (2000–2100).')
        elif not zone_id or 'month' in data:
            # Retain compatibility with clients that only send a calendar month.
            period=month_date(data.get('month'))
            same_series=zone_id and zone.repeats_annually and period.month==zone.date.month and period.year>=zone.date.year
            if not same_series and (not zone_id or zone.date.strftime('%Y-%m')!=period.strftime('%Y-%m')):
                zone.date=period
        zone.latitude=center.get('lat')
        zone.longitude=center.get('lng')
        zone.boundary=data.get('boundary')
        if type(data.get('active',True)) is not bool: raise ApiError('Active must be true or false.')
        zone.active=data.get('active',True)
        zone.updated_by=user
        zone.save()
        return {'zone':serialize_zone(zone)}
