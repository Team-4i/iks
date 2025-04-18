from django.urls import path
from . import views

app_name = 'hang'

urlpatterns = [
    path('', views.start_page, name='start_page'),
    path('play/', views.game, name='game'),
    path('play/<int:topic_group_id>/<int:summary_id>/', views.game, name='game_checkpoint'),
    path('end-game/', views.end_game, name='end_game'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
]
