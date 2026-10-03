from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Alert, Device, MonitoringArea, Report, UserProfile
from .accounts import EMAIL_ALREADY_REGISTERED, email_is_registered, normalize_email


COAST_GUARD_RANKS = [
    ('CG Commodore (CG COMMO)', 'CG Commodore (CG COMMO)'),
    ('CG Captain (CG CAPT)', 'CG Captain (CG CAPT)'),
    ('CG Commander (CG CDR)', 'CG Commander (CG CDR)'),
    ('CG Lieutenant Commander (CG LCDR)', 'CG Lieutenant Commander (CG LCDR)'),
    ('CG Lieutenant (CG LT)', 'CG Lieutenant (CG LT)'),
    ('CG Lieutenant Junior Grade (CG LTJG)', 'CG Lieutenant Junior Grade (CG LTJG)'),
    ('CG Ensign (CG ENS)', 'CG Ensign (CG ENS)'),
    ('CG Petty Officer First Class (PO1)', 'CG Petty Officer First Class (PO1)'),
    ('CG Petty Officer Second Class (PO2)', 'CG Petty Officer Second Class (PO2)'),
    ('CG Petty Officer Third Class (PO3)', 'CG Petty Officer Third Class (PO3)'),
    ('CG Seaman First Class (SN1)', 'CG Seaman First Class (SN1)'),
    ('CG Seaman Second Class (SN2)', 'CG Seaman Second Class (SN2)'),
    ('CG Apprentice Seaman (ASN)', 'CG Apprentice Seaman (ASN)'),
]


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=True, max_length=254)
    role = forms.ChoiceField(
        choices=[('', 'Select your rank'), *COAST_GUARD_RANKS],
        required=True,
    )
    station = forms.CharField(max_length=128, required=False)
    phone = forms.CharField(max_length=64, required=False)
    accepted_terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms and Conditions',
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError(
                'That username is already registered. Choose another username or sign in to your existing account.'
            )
        return username

    def clean_email(self):
        email = normalize_email(self.cleaned_data['email'])
        if email_is_registered(email):
            raise forms.ValidationError(EMAIL_ALREADY_REGISTERED)
        return email

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2',
        ]


class MonitoringAreaForm(forms.ModelForm):
    class Meta:
        model = MonitoringArea
        fields = ['label', 'latitude', 'longitude', 'image_url']
        widgets = {
            'label': forms.TextInput(attrs={'placeholder': 'Monitoring area name'}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
            'image_url': forms.URLInput(attrs={'placeholder': 'Optional image URL'}),
        }


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = [
            'name',
            'device_type',
            'water_level',
            'gyro',
            'gsm',
            'gps',
            'serial',
            'imei',
            'sim',
            'owner',
            'driver',
            'vessel',
            'registration',
            'contact',
            'status',
            'last_location',
            'last_updated',
            'photo',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Tracker name'}),
            'device_type': forms.TextInput(attrs={'placeholder': 'Water level / gyro / GSM / GPS tracker'}),
            'water_level': forms.CheckboxInput(),
            'gyro': forms.CheckboxInput(),
            'gsm': forms.CheckboxInput(),
            'gps': forms.CheckboxInput(),
            'serial': forms.TextInput(attrs={'placeholder': 'Serial number'}),
            'imei': forms.TextInput(attrs={'placeholder': 'IMEI / hardware ID'}),
            'sim': forms.TextInput(attrs={'placeholder': 'SIM number'}),
            'owner': forms.TextInput(attrs={'placeholder': 'Responsible officer'}),
            'driver': forms.TextInput(attrs={'placeholder': 'Driver / operator'}),
            'vessel': forms.TextInput(attrs={'placeholder': 'Vessel name'}),
            'registration': forms.TextInput(attrs={'placeholder': 'Registration ID'}),
            'contact': forms.TextInput(attrs={'placeholder': 'Contact phone'}),
            'status': forms.TextInput(attrs={'placeholder': 'Active / Offline'}),
            'last_location': forms.TextInput(attrs={'placeholder': 'Last known location'}),
            'last_updated': forms.TextInput(attrs={'placeholder': 'Last update timestamp'}),
        }
        labels = {
            'water_level': 'Water Level',
            'gyro': 'Gyro',
            'gsm': 'GSM',
            'gps': 'GPS',
        }


class AlertForm(forms.ModelForm):
    class Meta:
        model = Alert
        fields = ['type', 'location', 'time', 'severity', 'description']


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['type', 'location', 'severity', 'description']
        widgets = {
            'type': forms.TextInput(attrs={'placeholder': 'Incident type'}),
            'location': forms.TextInput(attrs={'placeholder': 'Incident location'}),
            'severity': forms.Select(choices=[('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')]),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the incident'}),
        }


class AccountForm(forms.ModelForm):
    email = forms.EmailField(required=True, max_length=254)

    def clean_email(self):
        email = normalize_email(self.cleaned_data['email'])
        if email_is_registered(email, exclude_user_id=self.instance.pk):
            raise forms.ValidationError(EMAIL_ALREADY_REGISTERED)
        return email

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class ProfileDetailsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'role', 'station', 'profile_image']


class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['notifications_enabled', 'alert_sound', 'share_location', 'dark_mode', 'language']
        widgets = {
            'alert_sound': forms.Select(choices=[
                ('Standard Marine Tone', 'Standard Marine Tone'),
                ('Emergency Beacon', 'Emergency Beacon'),
                ('Silent', 'Silent'),
            ]),
            'language': forms.Select(choices=[
                ('English', 'English'),
                ('Filipino', 'Filipino'),
                ('Cebuano', 'Cebuano'),
            ]),
        }
