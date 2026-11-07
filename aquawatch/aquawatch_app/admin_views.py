import json
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from .api import api, ApiError
from .zone_services import zones_result
from .models import Device, FishingZone
from .fishing import device_status_history

def require_admin(user):
    if not (user.is_staff or user.is_superuser): raise ApiError('Administrator access is required.',403)

def admin_records(user,kind):
    require_admin(user)
    if kind=='users':
        return {'users':[{'id':u.pk,'username':u.username,'email':u.email,'name':u.get_full_name(),
                         'is_admin':u.is_staff or u.is_superuser,'active':u.is_active,'device_count':u.device_count}
                        for u in User.objects.annotate(device_count=Count('device')).order_by('username')]}
    return {'devices':[{'id':d.pk,'name':d.name,'device_name':d.name,'device_type':d.device_type,
                       'mobile_id':d.mobile_id or f'web-{d.pk}',
                       'account':{'id':d.user_id,'name':d.user.get_full_name() or d.user.username,
                                  'username':d.user.username,'email':d.user.email},
                       'owner_name':d.owner,'driver':d.driver,'vessel':d.vessel,
                       'registration':d.registration,'contact':d.contact,'imei':d.imei,
                       'photo_url':d.photo.url if d.photo else '',
                       'serial':d.serial,'owner':d.user.username,
                       'email':d.user.email,'status':d.status,'last_location':d.last_location,
                       'last_updated':d.last_updated,'sim':d.sim}
                       for d in Device.objects.select_related('user').order_by('user__username','name')]}

@api(['GET','POST'])
def mobile_zones(request,data,zone_id=None):
    return zones_result(request.mobile_user,request.method,request.GET.get('month'),data,zone_id)

@api(['GET'])
def mobile_users(request,data): return admin_records(request.mobile_user,'users')

@api(['GET'])
def mobile_devices(request,data): return admin_records(request.mobile_user,'devices')

@api(['GET'])
def mobile_overview(request,data):
    require_admin(request.mobile_user)
    return {'users':User.objects.count(),'devices':Device.objects.count(),
            'zones':FishingZone.objects.filter(active=True).count()}

@api(['GET'])
def mobile_device_history(request,data,device_id):
    require_admin(request.mobile_user)
    device=Device.objects.filter(pk=device_id).first()
    if device is None: raise ApiError('Device not found.',404)
    return {'history':device_status_history(device)}

@login_required
def browser_zones(request,zone_id=None):
    try:
        if request.method not in ('GET','POST'): raise ApiError('Method not allowed.',405)
        data={}
        if request.method=='POST':
            if request.content_type!='application/json': raise ApiError('Send application/json.',415)
            if len(request.body)>512000: raise ApiError('Request too large.',413)
            try: data=json.loads(request.body)
            except ValueError: raise ApiError('Invalid JSON.')
            if not isinstance(data,dict): raise ApiError('Send a JSON object.')
        result=zones_result(request.user,request.method,request.GET.get('month'),data,zone_id)
        response=JsonResponse(result)
    except ApiError as error: response=JsonResponse({'error':error.message},status=error.status)
    except ValidationError as error: response=JsonResponse({'error':' '.join(error.messages)},status=400)
    response['Cache-Control']='no-store'
    return response

@login_required
def users_page(request):
    if not (request.user.is_staff or request.user.is_superuser): raise PermissionDenied()
    return render(request,'aquawatch_app/admin_users.html',admin_records(request.user,'users'))
