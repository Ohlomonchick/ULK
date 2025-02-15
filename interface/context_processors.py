from slugify import slugify
from interface.config import PNET_URL


def pnet_username(request):
    username = None
    if request.user.is_authenticated:
        if hasattr(request.user, 'pnet_login') and request.user.pnet_login is None:
            request.user.pnet_login = slugify(request.user.username)
            request.user.save()

        username = request.user.pnet_login
        return {'pnet_username': username, 'pnet_url': PNET_URL}
    return {}
