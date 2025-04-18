from django.contrib import admin
from .models import HangmanGame, PlayerStats

@admin.register(HangmanGame)
class HangmanGameAdmin(admin.ModelAdmin):
    list_display = ('player', 'start_time', 'end_time', 'survival_time', 'parts_revealed', 
                   'correct_answers', 'wrong_answers', 'is_active')
    list_filter = ('player', 'is_active', 'start_time')
    search_fields = ('player__username',)

@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    list_display = ('player', 'games_played', 'best_time', 'total_time', 
                   'total_correct_answers', 'total_wrong_answers')
    search_fields = ('player__username',)
