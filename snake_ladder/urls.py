from django.urls import path
from . import views

app_name = 'snake_ladder'

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_room, name='create_room'),
    path('join/<uuid:room_id>/', views.join_room, name='join_room'),
    path('board/<uuid:room_id>/', views.game_board, name='game_board'),
    path('game-state/<uuid:room_id>/', views.game_state, name='game_state'),
    path('room/<uuid:room_id>/', views.room_detail, name='room_detail'),
    path('generate-mcq/<uuid:room_id>/', views.generate_mcq, name='generate_mcq'),
    path('answer-mcq/<uuid:room_id>/', views.answer_mcq, name='answer_mcq'),
    path('report/<uuid:room_id>/', views.player_game_report, name='game_report'),
    path('api/room/<uuid:room_id>/state/', views.room_state, name='room_state'),
    path('api/room/<uuid:room_id>/start/', views.start_game, name='start_game'),
    path('room/<uuid:room_id>/generate-content/', views.generate_cell_content, name='generate_cell_content'),
    path('intro/', views.snake_ladder_intro, name='snake_ladder_intro'),
    path('cell-contents/', views.cell_content_details, name='cell_content_details'),
    path('update-bookmark/', views.update_bookmark, name='update_bookmark'),
]
