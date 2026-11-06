from datetime import date
from uuid import UUID
from django.db import transaction
from .models import FishingZone
from .api import ApiError

def month_date(value):
    try:
        result=date.fromisoformat(str(value)+'-01')
        if len(value)!=7 or not 2000<=result.year<=2100: raise ValueError()
        return result
    except (ValueError,TypeError):
        raise ApiError('Use a calendar month in YYYY-MM format (2000–2100).')

def serialize_zone(zone):
    return {'id':str(zone.pk),'title':zone.title,'month':zone.month.strftime('%Y-%m'),
            'center':{'lat':zone.latitude,'lng':zone.longitude},'boundary':zone.boundary,
            'area_square_meters':zone.area_square_meters,'active':zone.active,
            'version':zone.version,'proposed':True,'updated_at':zone.updated_at.isoformat()}

def zones_result(user, method, month=None, data=None, zone_id=None):
    if method=='GET':
        period=month_date(month)
        items=FishingZone.objects.filter(month=period)
        if not (user.is_staff or user.is_superuser): items=items.filter(active=True)
        return {'month':period.strftime('%Y-%m'),'zones':[serialize_zone(z) for z in items]}
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
        zone.title=title.strip()
        zone.month=month_date(data.get('month'))
        zone.latitude=center.get('lat')
        zone.longitude=center.get('lng')
        zone.boundary=data.get('boundary')
        if type(data.get('active',True)) is not bool: raise ApiError('Active must be true or false.')
        zone.active=data.get('active',True)
        zone.updated_by=user
        zone.save()
        return {'zone':serialize_zone(zone)}
