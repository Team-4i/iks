from django.urls import path
from . import views

app_name = 'dynamicDB'

urlpatterns = [
    path('', views.upload_pdf, name='upload_pdf'),
    path('view/<int:pk>/', views.view_pdf, name='view_pdf'),
    path('analyze/<int:pk>/', views.analyze_pdf, name='analyze_pdf'),
    path('visualize/<int:pk>/', views.visualize_topics, name='visualize_topics'),
    
    # Textbook-related URLs
    path('textbook/status/<int:pk>/', views.textbook_status, name='textbook_status'),
    path('textbook/view/<int:pk>/', views.view_textbook, name='view_textbook'),
    path('chapter/<int:pk>/', views.chapter_detail, name='chapter_detail'),
    path('topic/<int:pk>/', views.topic_detail, name='topic_detail'),
    
    # API for games
    path('api/content/<str:game_type>/', views.content_for_game, name='content_for_game'),
] 