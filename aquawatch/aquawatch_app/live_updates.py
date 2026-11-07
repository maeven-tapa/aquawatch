"""Small, account-scoped change signal for read-only web lists."""
import hashlib
import json
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Device,Report,MonitoringArea,UserProfile
from .alert_services import active_alerts

def shared_revision(user):
    admin=user.is_staff or user.is_superuser
    scope={} if admin else {'user':user}
    users=User.objects.all() if admin else User.objects.filter(pk=user.pk)
    data={
        'devices':list(Device.objects.filter(**scope).order_by('pk').values(
            'id','user_id','name','serial','sim','device_type','owner','driver','vessel','registration','contact','imei',
            'status','last_location','last_updated','last_status_at','photo','water_level','gyro','gsm','gps')),
        'users':list(users.order_by('pk').values('id','username','email','first_name','last_name','is_active','is_staff','is_superuser')),
        'alerts':list(active_alerts(None if admin else user).order_by('pk').values('id','type','severity','location','time','description')),
        'reports':list(Report.objects.filter(**scope).order_by('pk').values('id','type','severity','description','time','location')),
        'area':list(MonitoringArea.objects.filter(user=user).values('latitude','longitude','label','image_url')),
        'profile':list(UserProfile.objects.filter(user=user).values('role','station','phone')),
    }
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def live_page(view):
    @wraps(view)
    def wrapper(request,*args,**kwargs):
        # Capture before the view queries its displayed records. A write during
        # rendering may cause one harmless refresh, but cannot be missed forever.
        request.aqua_live_revision=shared_revision(request.user)
        return view(request,*args,**kwargs)
    return wrapper

@login_required
@require_GET
def sync_status(request):
    response=JsonResponse({'revision':shared_revision(request.user)})
    response['Cache-Control']='no-store'
    return response
