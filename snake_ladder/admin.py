from django.contrib import admin
from .models import Cell, GameRoom, PlayerPosition, CellHistory, CellContent, PlayerOverallPoints, GameFact

@admin.register(CellContent)
class CellContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'part', 'get_type_display', 'truncated_content')
    list_filter = ('part', 'type')
    search_fields = ('content', 'topic')
    ordering = ('part', 'type')

    def truncated_content(self, obj):
        """Display truncated content in list view"""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    truncated_content.short_description = 'Content Preview'

@admin.register(Cell)
class CellAdmin(admin.ModelAdmin):
    list_display = ('number', 'cell_type', 'get_current_content')
    list_filter = ('cell_type', 'current_content__part', 'current_content__type')
    search_fields = ('number', 'current_content__content', 'current_content__topic')
    ordering = ('number',)
    raw_id_fields = ('current_content',)

    def get_current_content(self, obj):
        """Display current content info in list view"""
        if obj.current_content:
            return f"Part {obj.current_content.part} - {obj.current_content.get_type_display()}"
        return "No content"
    get_current_content.short_description = 'Current Content'

@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = ('creator', 'room_id', 'current_turn', 'created_at', 'is_active', 'player_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('creator__username', 'room_id', 'players__username')
    date_hierarchy = 'created_at'
    raw_id_fields = ('creator', 'current_turn', 'winner')

    def player_count(self, obj):
        """Display number of players in room"""
        return obj.players.count()
    player_count.short_description = 'Players'

@admin.register(PlayerPosition)
class PlayerPositionAdmin(admin.ModelAdmin):
    list_display = ('player', 'room', 'position')
    list_filter = ('room', 'position')
    search_fields = ('player__username', 'room__room_id')
    raw_id_fields = ('player', 'room')

@admin.register(CellHistory)
class CellHistoryAdmin(admin.ModelAdmin):
    list_display = ('player', 'room', 'cell', 'visited_at', 'answer_correct', 'time_to_answer')
    list_filter = (
        'answer_correct',
        'difficulty_level',
        'visited_at',
        'cell__current_content__part',
        'cell__current_content__type'
    )
    search_fields = (
        'player__username',
        'cell__number',
        'question_text',
        'topic_category'
    )
    date_hierarchy = 'visited_at'
    raw_id_fields = ('player', 'room', 'cell')
    exclude = ['visited_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('player', 'room', 'cell', 'dice_roll')
        }),
        ('Question Details', {
            'fields': ('question_text', 'selected_answer', 'correct_answer', 'options')
        }),
        ('Performance', {
            'fields': (
                'answer_correct',
                'time_to_answer',
                'difficulty_level',
                'cumulative_score'
            )
        }),
        ('Movement', {
            'fields': ('source_cell', 'moves_after_answer')
        }),
        ('Analysis', {
            'fields': ('topic_category', 'attempt_number')
        })
    )

@admin.register(PlayerOverallPoints)
class PlayerOverallPointsAdmin(admin.ModelAdmin):
    list_display = ('player', 'total_points')
    search_fields = ('player__username',)
    ordering = ('-total_points',)  # Order by points descending
    raw_id_fields = ('player',)
    
    def get_readonly_fields(self, request, obj=None):
        # Make onlyplayer field readonly
        return ('player',)
    
    def save_model(self, request, obj, form, change):
        """Custom save method to handle point updates"""
        if change:
            old_obj = PlayerOverallPoints.objects.get(pk=obj.pk)
            if old_obj.total_points != obj.total_points:
                # Log the change
                self.message_user(
                    request, 
                    f"Total points updated for {obj.player.username}: {old_obj.total_points} → {obj.total_points}"
                )
                
                # Sync with platform points
                try:
                    from plat.models import PlayerPlatPoints
                    plat_points, _ = PlayerPlatPoints.objects.get_or_create(player=obj.player)
                    plat_points.update_points(obj.total_points, 'SNAKE_LADDER')
                    self.message_user(request, "Points synced with platform successfully")
                except Exception as e:
                    self.message_user(request, f"Error syncing with platform: {str(e)}", level='ERROR')
        
        super().save_model(request, obj, form, change)

@admin.register(GameFact)
class GameFactAdmin(admin.ModelAdmin):
    list_display = ('fact_text',)
    search_fields = ('fact_text',)
    list_per_page = 50

