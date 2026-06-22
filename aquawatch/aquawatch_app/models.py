from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=128, default='Coastal responder')
    station = models.CharField(max_length=128, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    dark_mode = models.BooleanField(default=True)
    language = models.CharField(max_length=32, default='English')
    notifications_enabled = models.BooleanField(default=True)
    share_location = models.BooleanField(default=True)
    alert_sound = models.CharField(max_length=64, default='Standard Marine Tone')
    profile_image = models.FileField(upload_to='profiles/', blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class MonitoringArea(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    label = models.CharField(max_length=128, default='Quiapo District Coast Watch')
    latitude = models.FloatField(default=14.5995)
    longitude = models.FloatField(default=120.9842)
    image_url = models.URLField(blank=True)

    def __str__(self):
        return self.label


class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    device_type = models.CharField(max_length=128, default='GPS tracker')
    serial = models.CharField(max_length=128)
    imei = models.CharField(max_length=128, blank=True)
    sim = models.CharField(max_length=64, blank=True)
    owner = models.CharField(max_length=128, blank=True)
    driver = models.CharField(max_length=128, blank=True)
    vessel = models.CharField(max_length=128, blank=True)
    registration = models.CharField(max_length=128, blank=True)
    contact = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=64, default='Active')
    last_location = models.CharField(max_length=128, blank=True)
    last_updated = models.CharField(max_length=64, blank=True)
    photo = models.FileField(upload_to='devices/', blank=True)

    def __str__(self):
        return self.name


class Alert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=128)
    location = models.CharField(max_length=128)
    time = models.CharField(max_length=64)
    severity = models.CharField(max_length=64)
    description = models.TextField(blank=True)

    def __str__(self):
        return f'{self.type} alert at {self.location}'


class Report(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=128)
    location = models.CharField(max_length=128)
    severity = models.CharField(max_length=64)
    time = models.CharField(max_length=64)
    description = models.TextField(blank=True)

    def __str__(self):
        return f'{self.type} report at {self.location}'
