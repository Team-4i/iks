from django.urls import path
from . import views

app_name = 'aicharacter'

urlpatterns = [
    path('', views.index, name='index'),
    path('get_response/', views.get_response, name='get_response'),
    path('text_to_speech/', views.text_to_speech, name='text_to_speech'),
    path('popup/', views.popup_view, name='popup'),
] 