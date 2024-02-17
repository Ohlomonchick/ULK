from django.urls import path

from interface.views import LabDetailView, LabListView, registration

urlpatterns = [
    path("<slug:slug>/", LabDetailView.as_view(), name="lab-detail"),
    path("", LabListView.as_view(), name="lab-list"),
    path('user/registration/', registration, name = "register_user")
]