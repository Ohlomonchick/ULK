from django.urls import path

from interface.views import LabDetailView, LabListView, registration, PlatoonListView, PlatoonDetailView, UserDetailView

urlpatterns = [
    path("platoons/<id>/", PlatoonDetailView.as_view(), name="platoon-detail"),
    path("platoons/", PlatoonListView.as_view(), name="platoon-list"),
    path('user/registration/', registration, name = "register_user"),
    path('user/<id>/', UserDetailView.as_view(), name = "user-detail"),
    path("<slug:slug>/", LabDetailView.as_view(), name="lab-detail"),
    path("", LabListView.as_view(), name="lab-list")
]