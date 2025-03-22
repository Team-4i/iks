from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from dbs.models import ConstitutionalArticle
from django.utils import timezone


class ArticleBookmark(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    part = models.IntegerField()
    type = models.CharField(max_length=4)
    page_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user']
        
class PlayerPlatPoints(models.Model):
    # List of all games in the platform
    GAME_CHOICES = [
        ('SNAKE_LADDER', 'Snake and Ladder'),
        ('HOUSIE', 'Constitutional Housie'),
        ('SPINWHEEL', 'Spin Wheel'),
        ('FLIPCARD', 'Flip Card')
    ]
    
    # Constitutional parts that player needs to complete
    PART_CHOICES = [
        (5, 'Part 5'),
        (6, 'Part 6')
    ]
    
    # Types of articles within each part
    TYPE_CHOICES = [
        ('JUD', 'Judiciary'),
        ('LEG', 'Legislative'),
        ('EXEC', 'Executive')
    ]

    # Points required to unlock each checkpoint (starting from Part 5 LEG)
    CHECKPOINT_REQUIREMENTS = {
        '5_LEG': 300,   # First points requirement: Part 5 Legislative
        '5_EXEC': 600,  # Second checkpoint: Part 5 Executive
        '6_JUD': 900,   # Third checkpoint: Part 6 Judiciary
        '6_LEG': 1200,  # Fourth checkpoint: Part 6 Legislative
        '6_EXEC': 1500  # Final checkpoint: Part 6 Executive
    }

    # Basic player info and progress tracking
    player = models.OneToOneField(User, on_delete=models.CASCADE)
    current_part = models.IntegerField(choices=PART_CHOICES, default=5)  # Which part player is on (5 or 6)
    current_type = models.CharField(max_length=4, choices=TYPE_CHOICES, default='JUD')  # Which type within part (JUD/LEG/EXEC)
    completed_checkpoints = models.JSONField(default=dict)  # Stores which checkpoints player has finished
    
    # Overall statistics
    total_points = models.IntegerField(default=0)  # Sum of all game points
    games_played = models.IntegerField(default=0)  # Total number of games played
    total_wins = models.IntegerField(default=0)    # Total number of games won
    
    # Points earned in each game
    snake_ladder_points = models.IntegerField(default=0)
    housie_points = models.IntegerField(default=0)
    spinwheel_coins = models.IntegerField(default=0)  # Renamed from spinwheel_points
    flipcard_points = models.IntegerField(default=0)
    
    # Game-specific statistics
    snake_ladder_games = models.IntegerField(default=0)
    snake_ladder_wins = models.IntegerField(default=0)
    
    housie_games = models.IntegerField(default=0)
    housie_wins = models.IntegerField(default=0)
    
    spinwheel_games = models.IntegerField(default=0)
    spinwheel_wins = models.IntegerField(default=0)
    
    flipcard_games = models.IntegerField(default=0)
    flipcard_wins = models.IntegerField(default=0)
    
    # Add fields to track card collections spinwheel
    common_cards = models.IntegerField(default=0)
    rare_cards = models.IntegerField(default=0)
    epic_cards = models.IntegerField(default=0)
    legendary_cards = models.IntegerField(default=0)
    total_cards = models.IntegerField(default=0)

    def __str__(self):
        """How this object appears in admin/print statements"""
        return f"{self.player.username}'s Platform Points"

    def get_required_points_for_checkpoint(self, part, type_):
        """
        Gets how many points needed for a checkpoint
        Example: get_required_points_for_checkpoint(5, 'JUD') returns 300
        """
        checkpoint_key = f"{part}_{type_}"
        return self.CHECKPOINT_REQUIREMENTS.get(checkpoint_key, 0)

    def can_unlock_checkpoint(self, part, type_):
        """
        Checks if player has enough points to unlock a checkpoint
        """
        # First checkpoint (Part 5 Judiciary) is always unlocked
        if part == 5 and type_ == 'JUD':
            return True
        
        # Get required points for this checkpoint
        checkpoint_key = f"{part}_{type_}"
        required_points = self.CHECKPOINT_REQUIREMENTS.get(checkpoint_key, 0)
        
        # Check if previous checkpoint is completed
        checkpoints = [
            (5, 'JUD'), (5, 'LEG'), (5, 'EXEC'),
            (6, 'JUD'), (6, 'LEG'), (6, 'EXEC')
        ]
        current_index = checkpoints.index((part, type_))
        
        # If not first checkpoint, check if previous is completed
        if current_index > 0:
            prev_part, prev_type = checkpoints[current_index - 1]
            prev_key = f"{prev_part}_{prev_type}"
            prev_required = self.CHECKPOINT_REQUIREMENTS.get(prev_key, 0)
            
            # If we have enough points for current and all previous checkpoints
            if self.total_points >= required_points and self.total_points >= prev_required:
                return True
            return False
        
        # Return True if we have enough points
        return self.total_points >= required_points

    def calculate_total_points(self):
        """Calculate total points from all games (excluding spinwheel coins)"""
        return (
            self.snake_ladder_points + 
            self.housie_points + 
            self.flipcard_points
        )  # Removed spinwheel_coins from total

    def save(self, *args, **kwargs):
        """Override save method to update checkpoints based on total points"""
        # First update total points
        self.total_points = self.calculate_total_points()
        
        print(f"[DEBUG] Saving player points - Total Points: {self.total_points}")
        
        # Define checkpoint requirements in order
        checkpoints = [
            (5, 'JUD', 0),      # Part 5 JUD - Always unlocked
            (5, 'LEG', 300),    # Part 5 LEG - 300 points
            (5, 'EXEC', 600),   # Part 5 EXEC - 600 points
            (6, 'JUD', 900),    # Part 6 JUD - 900 points
            (6, 'LEG', 1200),   # Part 6 LEG - 1200 points
            (6, 'EXEC', 1500)   # Part 6 EXEC - 1500 points
        ]
        
        # Find the highest unlocked checkpoint based on points
        highest_unlocked = (5, 'JUD')  # Default to first checkpoint
        
        for part, type_, required_points in checkpoints:
            if self.total_points >= required_points:
                checkpoint_key = f"{part}_{type_}"
                # Mark this checkpoint as completed if not already
                if checkpoint_key not in self.completed_checkpoints:
                    print(f"[DEBUG] Unlocking checkpoint: Part {part} {type_}")
                    self.completed_checkpoints[checkpoint_key] = {
                        'completed_at': timezone.now().isoformat(),
                        'points': self.total_points
                    }
                highest_unlocked = (part, type_)
        
        # Always update to highest unlocked checkpoint
        print(f"[DEBUG] Setting current position to highest unlocked: Part {highest_unlocked[0]} {highest_unlocked[1]}")
        self.current_part = highest_unlocked[0]
        self.current_type = highest_unlocked[1]
        
        # Call the original save method
        super().save(*args, **kwargs)

    def update_points(self, points, game_type):
        """Updates points for a specific game and handles checkpoint progression"""
        print("\n=== DEBUG: Platform Points Update ===")
        print(f"Game Type: {game_type}")
        print(f"New Points Value: {points}")
        
        # Update specific game points based on game type
        if game_type == 'SNAKE_LADDER':
            print(f"Current snake_ladder_points: {self.snake_ladder_points}")
            
            # Get overall points for comparison
            try:
                from snake_ladder.models import PlayerOverallPoints
                overall_points = PlayerOverallPoints.objects.get(player=self.player)
                print(f"Current overall points from snake ladder: {overall_points.total_points}")
                
                # Update snake_ladder_points to match overall points
                self.snake_ladder_points = overall_points.total_points
                print(f"Updated snake_ladder_points to match overall: {self.snake_ladder_points}")
                
            except Exception as e:
                print(f"Could not get overall points: {e}")
                # If we can't get overall points, use the provided points
                self.snake_ladder_points = points
                print(f"Falling back to provided points: {points}")
                
        elif game_type == 'HOUSIE':
            # Sync with housie points
            from housie_consti.models import PlayerPoints
            total_housie_points = PlayerPoints.objects.filter(
                player=self.player
            ).aggregate(total=models.Sum('points'))['total'] or 0
            
            print(f"Current housie_points: {self.housie_points}")
            print(f"New housie total: {total_housie_points}")
            
            # Only update if points are different
            if self.housie_points != total_housie_points:
                self.housie_points = total_housie_points
                
        elif game_type == 'FLIPCARD':
            print(f"Current flipcard_points: {self.flipcard_points}")
            self.flipcard_points = points
            print(f"Updated flipcard_points to: {points}")
        
        # Calculate and update total points
        old_total = self.total_points
        self.total_points = self.calculate_total_points()
        print(f"Platform total points: {old_total} → {self.total_points}")
        
        # Save changes
        self.save()
        
        # Final debug output
        print(f"=== Final Point Values ===")
        print(f"Snake Ladder Points: {self.snake_ladder_points}")
        print(f"Housie Points: {self.housie_points}")
        print(f"Flipcard Points: {self.flipcard_points}")
        print(f"Total Points: {self.total_points}")
        print("=== Platform Points Update Complete ===\n")

    def handle_admin_points_update(self):
        """Special method for handling admin updates"""
        # Update total points
        self.total_points = self.calculate_total_points()
        
        # Check and update checkpoint progress
        if self.can_unlock_checkpoint(self.current_part, self.current_type):
            if self.mark_checkpoint_complete():
                self.advance_to_next_checkpoint()
                self.save()

    def is_checkpoint_completed(self, part, type_):
        """
        Checks if a specific checkpoint is done
        Example: is_checkpoint_completed(5, 'JUD') -> True/False
        """
        checkpoint_key = f"{part}_{type_}"
        return checkpoint_key in self.completed_checkpoints

    def get_next_incomplete_checkpoint(self):
        """
        Finds the next checkpoint player needs to complete
        Returns tuple of (part, type) or None if all done
        Follows the order: 5_JUD -> 5_LEG -> 5_EXEC -> 6_JUD -> 6_LEG -> 6_EXEC
        """
        checkpoints = [
            (5, 'JUD'), (5, 'LEG'), (5, 'EXEC'),
            (6, 'JUD'), (6, 'LEG'), (6, 'EXEC')
        ]
        
        for part, type_ in checkpoints:
            if not self.is_checkpoint_completed(part, type_):
                return part, type_
        return None

    def get_checkpoint_progress(self):
        """
        Gets progress info for the learning journey map
        Returns dict with points and completion status for each checkpoint
        Used by profile view to show the map
        """
        progress = {}
        for part in [5, 6]:
            progress[part] = {}
            for type_ in ['JUD', 'LEG', 'EXEC']:
                checkpoint_key = f"{part}_{type_}"
                # Special case for Part 5 JUD (always unlocked, no points required)
                if part == 5 and type_ == 'JUD':
                    required_points = 0
                else:
                    required_points = self.CHECKPOINT_REQUIREMENTS.get(checkpoint_key, 0)
                
                progress[part][type_] = {
                    'required_points': required_points,
                    'completed': self.is_checkpoint_completed(part, type_),
                    'unlocked': self.can_unlock_checkpoint(part, type_)
                }
        return progress

    def update_game_stats(self):
        """
        Updates game statistics for all games and calculates totals
        """
        from snake_ladder.models import GameRoom  # Import here to avoid circular import
        
        # Update Snake & Ladder stats
        snake_ladder_games = GameRoom.objects.filter(players=self.player)
        self.snake_ladder_games = snake_ladder_games.count()
        self.snake_ladder_wins = snake_ladder_games.filter(winner=self.player).count()
        
        # TODO: Add similar stats for other games when their models are ready
        # Example:
        # housie_games = HousieRoom.objects.filter(players=self.player)
        # self.housie_games = housie_games.count()
        # self.housie_wins = housie_games.filter(winner=self.player).count()
        
        # Calculate totals
        self.games_played = (
            self.snake_ladder_games +
            self.housie_games +
            self.spinwheel_games +
            self.flipcard_games
        )
        
        self.total_wins = (
            self.snake_ladder_wins +
            self.housie_wins +
            self.spinwheel_wins +
            self.flipcard_wins
        )
        
        # Save the updated stats
        self.save()
        
        # Return detailed stats dictionary
        return {
            'total': {
                'games_played': self.games_played,
                'total_wins': self.total_wins,
                'win_rate': f"{(self.total_wins / self.games_played * 100):.1f}%" if self.games_played > 0 else "0%"
            },
            'snake_ladder': {
                'games': self.snake_ladder_games,
                'wins': self.snake_ladder_wins,
                'win_rate': f"{(self.snake_ladder_wins / self.snake_ladder_games * 100):.1f}%" if self.snake_ladder_games > 0 else "0%"
            },
            'housie': {
                'games': self.housie_games,
                'wins': self.housie_wins,
                'win_rate': f"{(self.housie_wins / self.housie_games * 100):.1f}%" if self.housie_games > 0 else "0%"
            },
            'spinwheel': {
                'games': self.spinwheel_games,
                'wins': self.spinwheel_wins,
                'win_rate': f"{(self.spinwheel_wins / self.spinwheel_games * 100):.1f}%" if self.spinwheel_games > 0 else "0%"
            },
            'flipcard': {
                'games': self.flipcard_games,
                'wins': self.flipcard_wins,
                'win_rate': f"{(self.flipcard_wins / self.flipcard_games * 100):.1f}%" if self.flipcard_games > 0 else "0%"
            }
        }

    def update_spinwheel_stats(self):
        """Update spinwheel statistics from PlayerCollection"""
        # Lazy import to avoid circular dependency
        from spinwheel.models import PlayerCollection
        
        # Get all cards for this player
        collections = PlayerCollection.objects.filter(player__user=self.player)
        
        # Reset counters
        self.common_cards = 0
        self.rare_cards = 0
        self.epic_cards = 0
        self.legendary_cards = 0
        
        # Count cards by rarity
        for collection in collections:
            if collection.card.rarity == 'COMMON':
                self.common_cards += collection.quantity
            elif collection.card.rarity == 'RARE':
                self.rare_cards += collection.quantity
            elif collection.card.rarity == 'EPIC':
                self.epic_cards += collection.quantity
            elif collection.card.rarity == 'LEGENDARY':
                self.legendary_cards += collection.quantity
        
        # Update total cards
        self.total_cards = (
            self.common_cards + 
            self.rare_cards + 
            self.epic_cards + 
            self.legendary_cards
        )
        
        self.save()

    def update_spinwheel_coins(self):
        """Update spinwheel coins from PlayerProfile"""
        from spinwheel.models import PlayerProfile
        try:
            profile = PlayerProfile.objects.get(user=self.player)
            self.spinwheel_coins = profile.coins
            self.save()
        except PlayerProfile.DoesNotExist:
            pass

    def sync_all_game_data(self):
        """Sync all game data from various game models"""
        try:
            print("\n=== Debugging from Plat: sync_all_game_data ===")
            print(f"Syncing data for player: {self.player.username}")
            
            # Sync Spinwheel data
            from spinwheel.models import PlayerProfile, PlayerCollection
            spinwheel_profile = PlayerProfile.objects.get(user=self.player)
            old_coins = self.spinwheel_coins
            self.spinwheel_coins = spinwheel_profile.coins
            print(f"Spinwheel Coins: {old_coins} → {self.spinwheel_coins}")
            
            # Update card counts
            old_cards = f"Common: {self.common_cards}, Rare: {self.rare_cards}, Epic: {self.epic_cards}"
            collections = PlayerCollection.objects.filter(
                player=spinwheel_profile,
                quantity__gt=0
            ).values('card__rarity').annotate(count=Count('card'))
            
            self.common_cards = self.rare_cards = self.epic_cards = 0
            for count_data in collections:
                if count_data['card__rarity'] == 'COMMON':
                    self.common_cards = count_data['count']
                elif count_data['card__rarity'] == 'RARE':
                    self.rare_cards = count_data['count']
                elif count_data['card__rarity'] == 'EPIC':
                    self.epic_cards = count_data['count']
            
            print(f"Cards: {old_cards} → Common: {self.common_cards}, Rare: {self.rare_cards}, Epic: {self.epic_cards}")
            
            # Sync Snake Ladder data
            from snake_ladder.models import PlayerOverallPoints
            try:
                snake_ladder_stats = PlayerOverallPoints.objects.get(player=self.player)
                old_points = self.snake_ladder_points
                self.snake_ladder_points = snake_ladder_stats.total_points
                print(f"Snake Ladder Points: {old_points} → {self.snake_ladder_points}")
            except PlayerOverallPoints.DoesNotExist:
                print("No Snake Ladder stats found")
            
            # Sync Housie data
            from housie_consti.models import PlayerStats
            try:
                housie_stats = PlayerStats.objects.get(player=self.player)
                old_points = self.housie_points
                self.housie_points = housie_stats.total_points
                print(f"Housie Points: {old_points} → {self.housie_points}")
            except PlayerStats.DoesNotExist:
                print("No Housie stats found")
            
            # Sync Flipcard data
            from flip_card.models import UserProgress
            try:
                flipcard_progress = UserProgress.objects.get(user=self.player)
                old_points = self.flipcard_points
                self.flipcard_points = flipcard_progress.total_points
                print(f"Flipcard Points: {old_points} → {self.flipcard_points}")
            except UserProgress.DoesNotExist:
                print("No Flipcard progress found")
            
            # Update totals
            old_total = self.total_points
            self.total_points = (
                self.snake_ladder_points +
                self.housie_points +
                self.flipcard_points
            )
            print(f"Total Points: {old_total} → {self.total_points}")
            
            self.save()
            print("=== Sync completed successfully ===\n")
            return True
            
        except Exception as e:
            print(f"=== Error syncing game data: {e} ===\n")
            return False

    class Meta:
        verbose_name = "Player Platform Points"
        verbose_name_plural = "Player Platform Points"
