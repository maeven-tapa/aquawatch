from django.contrib.auth.models import User
from django.db.models.functions import Lower, Trim


EMAIL_ALREADY_REGISTERED = 'This email is already registered. Sign in to your existing web or mobile account.'


def normalize_email(email):
    return email.strip().lower()


def email_is_registered(email, exclude_user_id=None):
    users = User.objects.alias(account_email=Lower(Trim('email'))).filter(account_email=normalize_email(email))
    if exclude_user_id is not None:
        users = users.exclude(pk=exclude_user_id)
    return users.exists()
