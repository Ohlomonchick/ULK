from django.urls import path
from .views import AnswerAPIView
from .api import *

urlpatterns = [
    path("answers", AnswerAPIView.as_view({'get': 'list', 'post': 'create'})),
    path("start", start_lab, name='start-lab'),
    path("end", end_lab, name='end-lab'),
    path('get_competition_time/<int:competition_id>/', get_time, name='get_time'),
    path('get_lab_levels/<path:lab_name>/', load_levels, name='load_levels'),
    path('lab_tasks/<path:lab_name>/', load_tasks, name='load_tasks'),
    path('press_button/<str:action>/', press_button, name='press_button'),
    path('check_availability/<slug:slug>/', check_availability, name='check_availability'),
    path('check_updates/', check_updates, name='check_updates'),
    path('get_users_in_platoons/', get_users_in_platoons, name='get_users_in_platoons'),
]
