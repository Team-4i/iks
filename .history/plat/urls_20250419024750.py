from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required

app_name = 'plat'

urlpatterns = [
    path('profile/', login_required(views.profile), name='profile'),
    path('checkpoint/<int:part>/<str:type>/', login_required(views.checkpoint_detail), name='checkpoint_detail'),
    path('topic-checkpoint/<int:topic_group_id>/<int:summary_id>/', login_required(views.topic_checkpoint), name='topic_checkpoint'),  #TOPIC GROUP IS MAIN TOPIC AND SUMMARY IS SUB TOPIC
    path('leaderboard/', login_required(views.leaderboard), name='leaderboard'),
    path('articles/<int:part>/<str:type>/', login_required(views.article_details), name='article_details'),
    path('add_bookmark/', login_required(views.add_bookmark), name='add_bookmark'),
    path('get_bookmark/', login_required(views.get_bookmark), name='get_bookmark'),
    path('get_speech/', login_required(views.get_speech), name='get_speech'),
] 
