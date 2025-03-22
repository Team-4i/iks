from django.contrib import admin
from .models import Article, Case, GameRoom, GameState, PlayerPoints
from django.utils.html import format_html
from django.contrib.auth.models import User

class ArticleAdmin(admin.ModelAdmin):
    list_display = ('article_number', 'title', 'part', 'type')
    list_filter = ('part', 'type')
    search_fields = ('title', 'article_number', 'content')
    ordering = ['article_number']
    fieldsets = (
        (None, {
            'fields': ('article_number', 'title')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Classification', {
            'fields': ('part', 'type')
        })
    )

class CaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'get_articles')
    list_filter = ('articles',)

    def get_articles(self, obj):
        return ", ".join([article.title for article in obj.articles.all()])
    get_articles.short_description = 'Articles'

class GameRoomAdmin(admin.ModelAdmin):
    list_display = ('room_id', 'creator', 'created_at', 'is_active', 'game_started')
    list_filter = ('is_active', 'game_started', 'created_at')
    search_fields = ('creator__username', 'room_id')
    readonly_fields = ('room_id', 'created_at', 'display_article_selection', 'display_selected_cards')

    def display_article_selection(self, obj):
        html = '<table><tr><th>Player</th><th>Assigned Articles</th></tr>'
        for player_id, articles in obj.article_selection.items():
            try:
                player = User.objects.get(id=int(player_id))
                articles_list = Article.objects.filter(id__in=articles)
                articles_str = '<br>'.join([f"{art.title}" for art in articles_list])
                html += f'<tr><td>{player.username}</td><td>{articles_str}</td></tr>'
            except Exception as e:
                html += f'<tr><td>Player {player_id}</td><td>Error: {str(e)}</td></tr>'
        html += '</table>'
        return format_html(html)

    def display_selected_cards(self, obj):
        html = '<table><tr><th>Player</th><th>Selected Articles</th><th>Points Update</th></tr>'
        for player_id, selected in obj.selected_cards.items():
            try:
                player = User.objects.get(id=int(player_id))
                selected_list = Article.objects.filter(id__in=selected)
                selected_str = '<br>'.join([f"{art.title}" for art in selected_list])
                
                # Check number of selected cards and update points if needed
                num_selected = len(selected)
                points_update = ""
                player_points, created = PlayerPoints.objects.get_or_create(
                    room=obj,
                    player=player,
                    defaults={'points': 0}
                )

                # Handle different point levels based on matches
                if num_selected >= 15:
                    if player_points.points < 100:  # If haven't received 15-match points yet
                        player_points.points = 100  # Total points for all levels
                        player_points.save()
                        points_update = f"Added 60 points for 15 matches! (Total: {player_points.points})"
                    else:
                        points_update = f"Game Complete! Total points: {player_points.points}"
                elif num_selected >= 10:
                    if player_points.points < 40:  # If haven't received 10-match points yet
                        player_points.points = 40  # Points for 5 and 10 matches
                        player_points.save()
                        points_update = f"Added 30 points for 10 matches! (Total: {player_points.points})"
                    else:
                        points_update = f"Current points: {player_points.points}"
                elif num_selected >= 5:
                    if player_points.points < 10:  # If haven't received 5-match points yet
                        player_points.points = 10  # Points for 5 matches
                        player_points.save()
                        points_update = f"Added 10 points for 5 matches! (Total: {player_points.points})"
                    else:
                        points_update = f"Current points: {player_points.points}"
                
                status = ""
                if num_selected >= 15:
                    status = '<span style="color: green; font-weight: bold;"> (Game Completed!)</span>'
                
                html += f'<tr><td>{player.username}</td><td>{selected_str}</td><td>{points_update}{status}</td></tr>'
            except Exception as e:
                html += f'<tr><td>Player {player_id}</td><td>Error: {str(e)}</td><td></td></tr>'
        html += '</table>'
        return format_html(html)

    display_article_selection.short_description = 'Player Article Assignments'
    display_selected_cards.short_description = 'Player Selected Articles'

class GameStateAdmin(admin.ModelAdmin):
    list_display = ('room', 'current_case_index', 'round_start_time', 'is_active')
    list_filter = ('is_active',)
    readonly_fields = ('round_start_time',)

class PlayerPointsAdmin(admin.ModelAdmin):
    list_display = ('player', 'room', 'points')
    list_filter = ('room',)
    search_fields = ('player__username',)

admin.site.register(Article, ArticleAdmin)
admin.site.register(Case, CaseAdmin)
admin.site.register(GameRoom, GameRoomAdmin)
admin.site.register(GameState, GameStateAdmin)
admin.site.register(PlayerPoints, PlayerPointsAdmin)
