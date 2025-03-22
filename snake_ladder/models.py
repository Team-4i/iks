from django.db import models
from django.contrib.auth.models import User
import uuid
import random

class CellContent(models.Model):
    """Model to store educational content segregated by part and type"""
    PART_CHOICES = [
        (5, 'Part 5'),
        (6, 'Part 6'),
    ]
    
    TYPE_CHOICES = [
        ('JUD', 'Judiciary'),
        ('LEG', 'Legislative'),
        ('EXEC', 'Executive'),
    ]

    content = models.TextField(help_text="Educational content")
    topic = models.CharField(max_length=100, null=True, blank=True)
    part = models.IntegerField(choices=PART_CHOICES, null=True, blank=True)
    type = models.CharField(max_length=4, choices=TYPE_CHOICES, null=True, blank=True)
    
    def __str__(self):
        part_display = f"Part {self.part}" if self.part else "No Part"
        type_display = self.get_type_display() if self.type else "No Type"
        return f"Content - {part_display} {type_display}: {self.topic or 'No topic'}"

    class Meta:
        ordering = ['part', 'type']

class Cell(models.Model):
    number = models.IntegerField(unique=True)
    cell_type = models.CharField(
        max_length=15,
        choices=[
            ('NORMAL', 'Normal Cell'),
            ('SNAKE_LADDER', 'Snake-Ladder Cell'),
        ],
        default='NORMAL'
    )
    # Change to Many-to-Many relationship
    contents = models.ManyToManyField(
        CellContent,
        related_name='cells',
        blank=True
    )
    # Reference to the currently active content
    current_content = models.ForeignKey(
        CellContent, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='displayed_on_cell'
    )
    
    # Hardcoded snake and ladder cells
    SNAKE_LADDER_CELLS = [
        # Skip first 5 cells (1-5)
        8, 15, 24, 28, 
        31, 37, 45, 49,
        52, 58, 61, 67,
        74, 78, 82, 85,
        91, 94, 97, 20,
    ]
    
    @classmethod
    def is_snake_ladder_cell(cls, number):
        """Helper method to check if a cell number is a snake/ladder cell"""
        return number in cls.SNAKE_LADDER_CELLS
    
    def save(self, *args, **kwargs):
        # Automatically set cell_type based on number
        self.cell_type = 'SNAKE_LADDER' if self.is_snake_ladder_cell(self.number) else 'NORMAL'
        super().save(*args, **kwargs)
    
    def set_current_content(self, part=None, type=None):
        """
        Set current_content based on part and type.
        If multiple matches exist, picks the first one.
        Returns True if content was set, False otherwise.
        """
        query = self.contents.all()
        if part:
            query = query.filter(part=part)
        if type:
            query = query.filter(type=type)
        
        content = query.first()
        if content:
            self.current_content = content
            self.save()
            return True
        return False
    
    def get_available_content_types(self):
        """Returns distinct part and type combinations available for this cell"""
        return self.contents.values('part', 'type').distinct()
    
    def __str__(self):
        return f"Cell {self.number}"

    class Meta:
        ordering = ['number']

class GameRoom(models.Model):
    room_id = models.UUIDField(default=uuid.uuid4, unique=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    players = models.ManyToManyField(User, related_name='joined_rooms')
    current_turn = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='current_turn_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='games_won')
    points = models.JSONField(default=dict)  # Stores points for each player in the game
    
    PLAYER_COLORS = {
        0: ('blue-500', 'Blue'),
        1: ('red-500', 'Red'),
        2: ('green-500', 'Green'),
        3: ('purple-500', 'Purple'),
    }
    
    # Add these new fields to track current content type
    current_content_part = models.IntegerField(
        choices=CellContent.PART_CHOICES,
        null=True
    )
    current_content_type = models.CharField(
        max_length=4,
        choices=CellContent.TYPE_CHOICES,
        null=True
    )
    
    def get_player_color(self):
        player_dict = {}
        player_list = list(self.players.all())
        for player in player_list:
            try:
                index = player_list.index(player)
                player_dict[player] = self.PLAYER_COLORS[index]
            except (ValueError, KeyError):
                player_dict[player] = ('gray-500', 'Gray')
        return player_dict
    
    def __str__(self):
        return f"Room by {self.creator.username}"

    def get_cell_history(self, player=None):
        """Get cell history for the room, optionally filtered by player"""
        history = CellHistory.objects.filter(room=self)
        if player:
            history = history.filter(player=player)
        return history.select_related('cell', 'player').order_by('-visited_at')

    def update_points(self, player_id, points_to_add):
        """Update points for a player in this game"""
        print("\n=== DEBUG: GameRoom Points Update ===")
        print(f"Player ID: {player_id}")
        print(f"Points to add: {points_to_add}")
        
        if not self.points:
            self.points = {}
        
        # Update game-specific points
        current_points = self.points.get(str(player_id), 0)
        print(f"Current game points: {current_points}")
        self.points[str(player_id)] = current_points + points_to_add
        print(f"New game points total: {self.points[str(player_id)]}")
        
        # Update overall points with debugging
        try:
            overall_points, created = PlayerOverallPoints.objects.get_or_create(player_id=player_id)
            print(f"Overall points before update: {overall_points.total_points}")
            overall_points.total_points += points_to_add
            overall_points.save()
            print(f"Overall points after update: {overall_points.total_points}")
            
            # Update platform points immediately after overall points
            try:
                from plat.models import PlayerPlatPoints
                plat_points = PlayerPlatPoints.objects.get(player_id=player_id)
                old_platform_points = plat_points.snake_ladder_points
                plat_points.snake_ladder_points = overall_points.total_points  # Sync with overall points
                plat_points.save()
                print(f"Platform points updated: {old_platform_points} → {plat_points.snake_ladder_points}")
                
                # Force recalculation of total points
                plat_points.total_points = plat_points.calculate_total_points()
                plat_points.save()
                print(f"Platform total points updated to: {plat_points.total_points}")
                
            except Exception as e:
                print(f"Could not update platform points: {e}")
                
        except Exception as e:
            print(f"Error updating overall points: {e}")
        
        self.save()
        print("=== GameRoom Points Update Complete ===\n")
    def get_player_points(self, player):
        """Get both game-specific and overall points for a player"""
        game_points = self.points.get(str(player.id), 0)
        overall_points = PlayerOverallPoints.objects.get_or_create(player=player)[0].total_points
        return {
            'game_points': game_points,
            'overall_points': overall_points
        }

    def set_game_content_type(self, part=None, type=None):
        """Set content type for the entire game"""
        print(f"[DEBUG] Setting game content - Part: {part}, Type: {type}")  # Debug log
        
        self.current_content_part = part
        self.current_content_type = type
        self.save()
        
        # Update all normal cells with content of this type
        normal_cells = Cell.objects.filter(cell_type='NORMAL')
        available_content = CellContent.objects.filter(
            part=part,
            type=type
        )
        
        print(f"[DEBUG] Found {available_content.count()} content items for Part {part} Type {type}")  # Debug log
        
        content_list = list(available_content)
        
        for cell in normal_cells:
            if content_list:
                content = random.choice(content_list)
                content_list.remove(content)
                cell.current_content = content
                cell.save()
            else:
                print(f"[DEBUG] Warning: No content left for Cell {cell.number}")  # Debug log

class PlayerPosition(models.Model):
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='player_positions')
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    position = models.IntegerField(default=1)

    class Meta:
        unique_together = ('room', 'player')

class CellHistory(models.Model):
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE)
    cell = models.ForeignKey(Cell, on_delete=models.CASCADE)
    visited_at = models.DateTimeField(auto_now_add=True, editable=True)
    
    # Enhanced question tracking
    question_text = models.TextField(null=True)
    selected_answer = models.CharField(max_length=255, null=True)
    correct_answer = models.CharField(max_length=255, null=True)
    answer_correct = models.BooleanField(null=True)
    time_to_answer = models.IntegerField(null=True)
    
    # New fields for better analysis
    topic_category = models.CharField(max_length=100, null=True)
    difficulty_level = models.CharField(
        max_length=20,
        choices=[('EASY', 'Easy'), ('MEDIUM', 'Medium'), ('HARD', 'Hard')],
        null=True
    )
    moves_after_answer = models.IntegerField(null=True)  # Track movement after answer
    cumulative_score = models.IntegerField(default=0)    # Running score in the game
    attempt_number = models.IntegerField(default=1)      # Which attempt at this topic
    
    # Add field for storing options
    options = models.TextField(null=True)  # Will store JSON string of options array
    
    # Add this field
    source_cell = models.IntegerField(null=True, blank=True)
    
    dice_roll = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-visited_at']
        indexes = [
            models.Index(fields=['player', 'room']),
            models.Index(fields=['player', 'answer_correct']),  # For quick stats queries
        ]
    
    def __str__(self):
        return f"{self.player.username} visited cell {self.cell.number} in room {self.room.room_id}"

class PlayerOverallPoints(models.Model):
    player = models.OneToOneField(User, on_delete=models.CASCADE)
    total_points = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.player.username} - {self.total_points} points"

class CellBookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    page_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user',)
