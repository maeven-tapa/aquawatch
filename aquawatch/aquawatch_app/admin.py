from django.contrib import admin
from .models import FishingZone, Device, DeviceReading, UserProfile, MonitoringArea, Report, Alert, AlertDismissal

@admin.register(FishingZone)
class FishingZoneAdmin(admin.ModelAdmin):
    change_form_template = 'admin/aquawatch_app/fishingzone/change_form.html'
    list_display = ('title','date','repeats_annually','area_square_meters','active','published_at','updated_at')
    list_filter = ('date','repeats_annually','active')
    search_fields = ('title','source_id')
    readonly_fields = ('area_square_meters','version','published_at','updated_at','updated_by','source_id')
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        from .zone_geometry import ENVELOPE
        extra_context = dict(extra_context or {}, zone_envelope=[{'lat':lat,'lng':lng} for lng,lat in ENVELOPE])
        return super().changeform_view(request, object_id, form_url, extra_context)
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
