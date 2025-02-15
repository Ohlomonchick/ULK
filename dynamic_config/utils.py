from .models import ConfigEntry


def get_config(key, default=None):
    try:
        entry = ConfigEntry.objects.get(key=key)
        return entry.value
    except ConfigEntry.DoesNotExist:
        return default
