from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='admin2')
print(user.is_active)