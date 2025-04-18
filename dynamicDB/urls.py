from django.urls import path
from . import views

app_name = 'dynamicDB'

urlpatterns = [
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('view/<int:pk>/', views.view_pdf, name='view_pdf'),
    path('analyze_pdf/<int:pk>/', views.analyze_pdf, name='analyze_pdf'),
    path('visualize/<int:pk>/', views.visualize_topics, name='visualize_topics'),
] 