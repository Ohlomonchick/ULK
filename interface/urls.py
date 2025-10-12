from django.urls import path

from interface.views import *

urlpatterns = [
    path("platoons/<id>/", PlatoonDetailView.as_view(), name="platoon-detail"),
    path("platoons/", PlatoonListView.as_view(), name="platoon-list"),
    path('user/<id>/', UserDetailView.as_view(), name = "user-detail"),
    path("labs/<slug:slug>/<str:lab_type>/", LabDetailView.as_view(), name="lab-detail"),
    path("lab_menu/", lambda request: render(request, "interface/lab_menu.html"), name="lab-menu"),  # for /labs
    path("labs/", LabListView.as_view(), name="lab-list"),  # for /labs/?...
    path("competitions/<slug:slug>/kibana_dashboard/", kibana_dashboard, name="kibana-dashboard"),
    path("competitions/<slug:slug>/", CompetitionDetailView.as_view(), name="competition-detail"),
    path("team_competitions/<slug:slug>/", TeamCompetitionDetailView.as_view(), name="team-competition-detail"),
    path("competitions/", CompetitionListView.as_view(), name="competition-list"),
    path("competition_history/", CompetitionHistoryListView.as_view(), name="competition-history-list"),
    path("team_competitions/", TeamCompetitionListView.as_view(), name="team-competition-list"),
    path("help_page/", lambda request: render(request, "interface/help_page.html"), name="help-page"),
    path("utils/console/<slug:slug>/<str:node_name>/", utils_console, name="utils-console"),
    path('kkz/create/', CreateKkzView.as_view(), name='kkz-create'),
    path('kkz/create-from-lab/<str:lab_type>/<slug:slug>/', CreateKkzFromLabView.as_view(), name='kkz-create-from-lab'),
]