from django.urls import path
from .views import AnswerAPIView
from .api import *

urlpatterns = [
    path("answers", AnswerAPIView.as_view({'get': 'list', 'post': 'create'}), name='answer-list'),
    path("start", start_lab, name='start-lab'),
    path("end", end_lab, name='end-lab'),
    path('get_competition_time/<int:competition_id>/', get_time, name='get_time'),
    path('get_lab_levels/<path:lab_name>/', load_levels, name='load_levels'),
    path('lab_tasks/<path:lab_name>/', load_tasks, name='load_tasks'),
    path('press_button/<str:action>/', press_button, name='press_button'),
    path('check_availability/<slug:slug>/', check_availability, name='check_availability'),
    path('check_updates/', check_updates, name='check_updates'),
    path('get_users_in_platoons/', get_users_in_platoons, name='get_users_in_platoons'),
    path('get_competition_solutions/<slug:slug>/', get_solutions, name='get_solutions'),
    path('get_pnet_auth/', get_pnet_auth, name='get_pnet_auth'),
    path('get_kibana_auth/', get_kibana_auth, name='get_kibana_auth'),
    path('check_kibana_auth_status/', check_kibana_auth_status, name='check_kibana_auth_status'),
    path('create_pnet_lab_session/', create_pnet_lab_session, name='create_pnet_lab_session'),
    path('create_pnet_lab_session_with_console/', create_pnet_lab_session_with_console, name='create_pnet_lab_session_with_console'),
    path('kkz_preview_random/', kkz_preview_random, name='kkz_preview_random'),
    path('kkz_save_preview/', kkz_save_preview, name='kkz_save_preview'),
    path('get_labs_for_platoon/', get_labs_for_platoon, name='get-labs-for-platoon'),
    path('get_users_for_platoon/', get_users_for_platoon, name='get_users_for_platoon'),
]
