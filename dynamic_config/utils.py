from .models import ConfigEntry


def get_config(key, default=None):
    try:
        entry = ConfigEntry.objects.get(key=key)
        return entry.value
    except ConfigEntry.DoesNotExist:
        return default


def get_bool_config(key, default=False):
    value = get_config(key, None)
    if value is None:
        return default
    return str(value).lower() in ("true", "1", "yes", "on", "да", "вкл", "разрешить")