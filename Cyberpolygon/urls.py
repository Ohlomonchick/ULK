"""
URL configuration for Cyberpolygon project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from interface.views import registration, AnswerAPIView, change_password
from interface.api import get_time, get_solutions, press_button, check_updates, check_availability

admin.site.site_url = '/cyberpolygon/lab_menu'

urlpatterns = [
    path('', registration, name="reg"),
    path('api/', include('rest_framework.urls')),
    path("api/answers", AnswerAPIView.as_view({'get': 'list', 'post': 'create'})),
    path('api/get_competition_time/<int:competition_id>/', get_time, name='get_time'),
    path('api/get_competition_solutions/<slug:slug>/', get_solutions, name='get_solutions'),
    path('api/press_button/<str:action>/', press_button, name='press_button'),
    path('api/check_availability/<slug:slug>/', check_availability, name='check_availability'),
    path('api/check_updates/', check_updates, name='check_updates'),
    path('jet/', include('jet.urls', 'jet')),
    path('cyberpolygon/', include(('interface.urls', 'interface'), namespace='interface')),
    path('admin/', admin.site.urls),
    path('summernote/', include('django_summernote.urls')),
    path("select2/", include("django_select2.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("registration/change_password", change_password, name="change_password"),
    path('api/', include(('interface.api_urls', 'interface'), namespace='interface_api'))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

