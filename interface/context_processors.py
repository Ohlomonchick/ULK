from slugify import slugify


def pnet_username(request):
    username = None
    if request.user.is_authenticated:
        username = request.user.username
        return {'pnet_username': slugify(username)}
    return {}
