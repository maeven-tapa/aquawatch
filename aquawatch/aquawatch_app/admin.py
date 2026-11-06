from django.contrib import admin
from .models import FishingZone, Device, DeviceReading, UserProfile, MonitoringArea, Report, Alert, AlertDismissal

@admin.register(FishingZone)
class FishingZoneAdmin(admin.ModelAdmin):
    list_display = ('title','month','area_square_meters','active','updated_at')
    list_filter = ('month','active')
    search_fields = ('title','source_id')
    readonly_fields = ('area_square_meters','version','updated_at','updated_by','source_id')
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request,obj,form,change)

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display=('name','serial','user','status')
    search_fields=('name','serial','user__username','user__email')
    list_filter=('status',)

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display=('type','user','device','severity','time')
    search_fields=('source_id','type','user__username','device__name')

@admin.register(AlertDismissal)
class AlertDismissalAdmin(admin.ModelAdmin):
    list_display=('user','alert_key','dismissed_at')
    readonly_fields=('dismissed_at',)

admin.site.register([DeviceReading,UserProfile,MonitoringArea,Report])
admin.site.site_header = 'AquaWatch administration'
