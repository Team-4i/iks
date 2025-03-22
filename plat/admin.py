from django.contrib import admin
from django.contrib.auth.models import User
from .models import PlayerPlatPoints

@admin.register(PlayerPlatPoints)
class PlayerPlatPointsAdmin(admin.ModelAdmin):
    # List view configuration
    list_display = (
        'player',
        'total_points',
        'current_part',
        'current_type',
        'games_played',
        'total_wins',
        'snake_ladder_points',
        'housie_points',
        'spinwheel_coins',
        'flipcard_points'
    )
    
    # Filtering options in sidebar
    list_filter = (
        'current_part',
        'current_type',
        'player__is_active',  # Add filter for active/inactive users
        'player__date_joined',  # Add filter for join date
    )
    
    # Search configuration
    search_fields = (
        'player__username',
        'player__email',
        'player__first_name',
        'player__last_name',
    )
    
    # Default ordering
    ordering = ('-total_points', 'player__username')
    
    # Fields grouped in detail view
    fieldsets = (
        ('Player Info', {
            'fields': ('player',)
        }),
        ('Game Points', {
            'fields': (
                'snake_ladder_points',
                'housie_points',
                'spinwheel_coins',
                'flipcard_points'
            )
        }),
        ('Progress Tracking', {
            'fields': (
                'current_part',
                'current_type',
                'completed_checkpoints'
            )
        }),
        ('Statistics', {
            'fields': (
                'total_points',
                'games_played',
                'total_wins'
            )
        })
    )
    
    # Make certain fields read-only
    readonly_fields = (
        'total_points',
        'games_played',
        'total_wins',
        'completed_checkpoints'
    )
    
    def save_model(self, request, obj, form, change):
        """Custom save method to handle point updates"""
        # Store old values before save
        if change:
            old_obj = PlayerPlatPoints.objects.get(pk=obj.pk)
            old_points = {
                'snake_ladder': old_obj.snake_ladder_points,
                'housie': old_obj.housie_points,
                'spinwheel': old_obj.spinwheel_coins,
                'flipcard': old_obj.flipcard_points
            }
        
        # Save the model
        super().save_model(request, obj, form, change)
        
        # Recalculate total points and update checkpoints
        obj.total_points = obj.calculate_total_points()
        obj.save()
        
        # Log changes
        if change:
            if old_points['snake_ladder'] != obj.snake_ladder_points:
                self.message_user(request, f"Snake Ladder points updated: {old_points['snake_ladder']} → {obj.snake_ladder_points}")
            if old_points['housie'] != obj.housie_points:
                self.message_user(request, f"Housie points updated: {old_points['housie']} → {obj.housie_points}")
            if old_points['spinwheel'] != obj.spinwheel_coins:
                self.message_user(request, f"Spinwheel points updated: {old_points['spinwheel']} → {obj.spinwheel_coins}")
            if old_points['flipcard'] != obj.flipcard_points:
                self.message_user(request, f"Flipcard points updated: {old_points['flipcard']} → {obj.flipcard_points}")
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only"""
        if obj:  # Editing existing object
            return ('total_points', 'player')
        return ('total_points',)  # New object
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/custom_admin.js',)

    def has_delete_permission(self, request, obj=None):
        """Prevent accidental deletion of progress"""
        return False

    def get_queryset(self, request):
        """
        Override queryset to create PlayerPlatPoints for users who don't have one
        """
        # Get all existing PlayerPlatPoints
        qs = super().get_queryset(request)
        
        # Get all users who don't have PlayerPlatPoints
        users_without_points = User.objects.exclude(
            id__in=PlayerPlatPoints.objects.values_list('player_id', flat=True)
        )
        
        # Create PlayerPlatPoints for users who don't have them
        for user in users_without_points:
            PlayerPlatPoints.objects.create(player=user)
        
        # Return updated queryset
        return PlayerPlatPoints.objects.all()
