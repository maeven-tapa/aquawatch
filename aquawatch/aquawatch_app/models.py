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
    mobile_id = models.CharField(max_length=128, null=True, blank=True)
    last_status_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=128)
    device_type = models.CharField(max_length=128, default='GPS tracker')
    water_level = models.BooleanField(default=True)
    gyro = models.BooleanField(default=True)
    gsm = models.BooleanField(default=True)
    gps = models.BooleanField(default=True)
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

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'mobile_id'], name='device_user_mobile_id')]

    def __str__(self):
        return self.name

    @property
    def capability_labels(self):
        capabilities = [
            (self.water_level, 'Water Level'),
            (self.gyro, 'Gyro'),
            (self.gsm, 'GSM'),
            (self.gps, 'GPS'),
        ]
        return [label for enabled, label in capabilities if enabled]


class Alert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    source_id = models.CharField(max_length=256, blank=True)
    type = models.CharField(max_length=128)
    location = models.CharField(max_length=128)
    time = models.CharField(max_length=64)
    severity = models.CharField(max_length=64)
    description = models.TextField(blank=True)

    def __str__(self):
        return f'{self.type} alert at {self.location}'


class Report(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    mobile_id = models.CharField(max_length=128, null=True, blank=True)
    type = models.CharField(max_length=128)
    location = models.CharField(max_length=128)
    severity = models.CharField(max_length=64)
    time = models.CharField(max_length=64)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'mobile_id'], name='report_user_mobile_id')]

    def __str__(self):
        return f'{self.type} report at {self.location}'


class MobileToken(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    password_signature = models.CharField(max_length=64)
    expires_at = models.DateTimeField()


class SignupChallenge(models.Model):
    email = models.CharField(max_length=254, primary_key=True)
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)


class MobileAuthWindow(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class SyncReceipt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=128)
    payload_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'event_id'], name='sync_user_event_id')]


class DeviceReading(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='readings')
    received_at = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    gyro_x = models.CharField(max_length=64, blank=True)
    gyro_y = models.CharField(max_length=64, blank=True)
    gsm_signal = models.CharField(max_length=128, blank=True)
    acceleration = models.CharField(max_length=128, blank=True)
    water_level_value = models.CharField(max_length=128, blank=True)
    is_distress = models.BooleanField(default=False)
    alert_type = models.CharField(max_length=128, blank=True)

    class Meta:
        indexes = [models.Index(fields=['device', '-received_at'], name='reading_device_time')]
