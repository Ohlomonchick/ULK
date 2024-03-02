from django.urls import path

from interface.views import *

urlpatterns = [
    path("platoons/<id>/", PlatoonDetailView.as_view(), name="platoon-detail"),
    path("platoons/", PlatoonListView.as_view(), name="platoon-list"),
    path('user/registration/', registration, name = "register_user"),
    path('user/<id>/', UserDetailView.as_view(), name = "user-detail"),
    path("labs/<slug:slug>/", LabDetailView.as_view(), name="lab-detail"),
    path("labs", LabListView.as_view(), name="lab-list"),
    path("competitions/<slug:slug>/", CompetitionDetailView.as_view(), name="competition-detail"),
    path("competitions/", CompetitionListView.as_view(), name="competition-list"),
]