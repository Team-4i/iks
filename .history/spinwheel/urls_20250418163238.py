from django.urls import path
from . import views

app_name = 'spinwheel'

urlpatterns = [
    path('', views.index, name='index'),
    path('intro/', views.spinwheel_intro, name='spinwheel_intro'),
    path('collection/', views.collection, name='collection'),
    path('spin/', views.spin, name='spin'),
    path('marketplace/', views.marketplace, name='marketplace'),
    path('marketplace/sell/<int:card_id>/', views.sell_card, name='sell_card'),
    path('marketplace/buy/<int:card_id>/', views.buy_card, name='buy_card'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('card_combos/', views.card_combos, name='card_combos'),
] 