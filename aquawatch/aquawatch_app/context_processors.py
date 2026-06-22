from .models import UserProfile


def aquawatch_preferences(request):
    if not request.user.is_authenticated:
        return {'aqua_profile': None, 'aqua_language': 'English', 'aqua_dark_mode': True}
    try:
        profile = request.user.userprofile
    except (AttributeError, UserProfile.DoesNotExist):
        profile = None
    return {
        'aqua_profile': profile,
        'aqua_language': profile.language if profile else 'English',
        'aqua_dark_mode': profile.dark_mode if profile else True,
    }
