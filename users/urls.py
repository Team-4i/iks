from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('analytics/', views.analytics, name='analytics'),
    path('complete-profile/', views.complete_profile, name='complete_profile'),
    path('', views.landing_page, name='index'),  
    path('home/', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'), 
    path('chat/', views.chat, name='chat'),
    path('learn/', views.learn, name='learn'),  
    path('case-study/', views.case_study, name='case_study'),  
    path('learn/', views.learn, name='learn'),
    path('game-library/', views.game_library, name='game_library'),
    path('overall-analytics/', views.overall_analytics, name='overall_analytics'),
    path('map/', views.analytics_view, name='map'),
    path('analytics/export/<str:format>/', views.export_analytics, name='export_analytics'),
    path('profile/details/', views.profile_details, name='profile_details'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]
