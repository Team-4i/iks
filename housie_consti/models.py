from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
import random
import logging

logger = logging.getLogger(__name__)

class GameRoom(models.Model):
    room_id = models.UUIDField(default=uuid.uuid4, unique=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_housie_rooms')
    players = models.ManyToManyField(User, related_name='joined_housie_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    game_started = models.BooleanField(default=False)
    case_order = models.JSONField(null=True, blank=True)
    current_case_index = models.IntegerField(default=0)
    round_start_time = models.DateTimeField(null=True, blank=True)
    article_selection = models.JSONField(null=True, blank=True, default=dict)
    selected_cards = models.JSONField(default=dict)
    wrong_selections = models.JSONField(null=True, blank=True, default=dict)
    selection_times = models.JSONField(null=True, blank=True, default=dict)
    part = models.IntegerField(null=True, blank=True)
    type = models.CharField(max_length=3, null=True, blank=True)
    
    def __str__(self):
        return f"Housie Room by {self.creator.username}"

    def assign_articles_to_player(self, player_id, articles):
        """Assigns a list of articles to a player."""
        player_id = str(player_id)
        self.article_selection[player_id] = articles
        self.save()

    def mark_card_selected(self, player_id, article_id):
        """Marks an article as selected by a player and handles points."""
        player_id = str(player_id)
        
        # Get current case
        current_case = self.get_current_case()
        if not current_case:
            return False
        
        try:
            # Get the selected article and current case
            selected_article = Article.objects.get(id=article_id)
            case = Case.objects.get(id=current_case['id'])
            
            # Check if the article is in the current case's articles
            is_correct = case.articles.filter(id=article_id).exists()
            
            if is_correct:
                # Initialize selected cards for player if needed
                if player_id not in self.selected_cards:
                    self.selected_cards[player_id] = []
                    
                # Check if article was already selected
                if article_id not in self.selected_cards[player_id]:
                    self.selected_cards[player_id].append(article_id)
                    
                    # Get or create player points
                    player = User.objects.get(id=int(player_id))
                    player_points, _ = PlayerPoints.objects.get_or_create(
                        room=self,
                        player=player,
                        defaults={'points': 0}
                    )
                    
                    # Update points based on milestones
                    num_selected = len(self.selected_cards[player_id])
                    points_to_add = 0
                    
                    # Calculate points based on number of matches
                    if num_selected == 5:  # First line
                        points_to_add = 10
                    elif num_selected == 10:  # Second line
                        points_to_add = 30
                    elif num_selected == 15:  # Full house
                        points_to_add = 60
                    else:  # Add points for each correct match
                        points_to_add = 2  # Add 2 points for each correct match
                    
                    # Update points
                    player_points.points += points_to_add
                    player_points.correct_answers = num_selected
                    player_points.save()
                    
                    # If player completed full house, handle game completion
                    if num_selected == 15:
                        self.handle_game_completion(player_id)
                    
                    self.save()
                    return True
                    
            return False
            
        except (Case.DoesNotExist, Article.DoesNotExist, User.DoesNotExist) as e:
            logger.error(f"Error in mark_card_selected: {str(e)}")
            return False

    def handle_game_completion(self, player_id):
        """Handle game completion for a player who has matched 15 cards."""
        try:
            player = User.objects.get(id=int(player_id))
            # You can add additional game completion logic here
            # For example, notify other players, update leaderboard, etc.
            
            # Get total points for this player
            player_points = PlayerPoints.objects.get(room=self, player=player)
            print(f"Game completed for {player.username} with total points: {player_points.points}")
            
            # You might want to store the completion time
            if 'game_completion' not in self.selected_cards:
                self.selected_cards['game_completion'] = {}
            self.selected_cards['game_completion'][player_id] = timezone.now().isoformat()
            self.save()
            
        except Exception as e:
            print(f"Error handling game completion: {str(e)}")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def record_wrong_selection(self, player_id, article_id, case_id):
        """Records when a player makes a wrong selection"""
        player_id = str(player_id)
        if player_id not in self.wrong_selections:
            self.wrong_selections[player_id] = []
            
        self.wrong_selections[player_id].append({
            'article_id': article_id,
            'case_id': case_id,
            'timestamp': timezone.now().isoformat()
        })
        self.save()

    def record_selection_time(self, player_id, article_id, case_id, time_taken):
        """Records the time taken for a selection"""
        player_id = str(player_id)
        if player_id not in self.selection_times:
            self.selection_times[player_id] = []
            
        self.selection_times[player_id].append({
            'article_id': article_id,
            'case_id': case_id,
            'time_taken': time_taken,  # Time taken in seconds
            'total_time': 15,  # Total allowed time
            'timestamp': timezone.now().isoformat()
        })
        self.save()

    def get_current_case(self):
        """Get the current case with all its details"""
        if not self.case_order or not self.game_started:
            return None
        
        try:
            current_case_id = self.case_order[self.current_case_index]
            case = Case.objects.prefetch_related('articles').get(id=current_case_id)
            return {
                'id': case.id,
                'title': case.title,
                'description': case.description,
                'articles': [
                    {
                        'id': art.id,
                        'article_number': art.article_number,
                        'title': art.title
                    }
                    for art in case.articles.all()
                ]
            }
        except (IndexError, Case.DoesNotExist, TypeError):
            return None

    def get_time_remaining(self):
        """Calculate time remaining in current round"""
        if not self.round_start_time:
            return 15
        elapsed_time = (timezone.now() - self.round_start_time).total_seconds()
        return max(0, 15 - int(elapsed_time))

    def advance_case(self):
        """Advance to next case and reset timer"""
        if self.case_order:
            self.current_case_index = (self.current_case_index + 1) % len(self.case_order)
            self.round_start_time = timezone.now()
            self.save()

    def start_game(self, part=None, type=None):
        """Initialize game with filtered case order and start time"""
        if not self.game_started:
            # Store part and type if provided
            if part is not None:
                self.part = part
            if type is not None:
                self.type = type
            
            # Filter cases based on part and type if provided
            cases_query = Case.objects.all()
            if part is not None:
                cases_query = cases_query.filter(part=part)
            if type is not None:
                cases_query = cases_query.filter(type=type)
            
            all_cases = list(cases_query.values_list('id', flat=True))
            
            if not all_cases:
                raise ValueError("No cases found matching the specified criteria")
            
            self.case_order = random.sample(all_cases, len(all_cases))
            self.game_started = True
            self.save()
            
            # Initialize GameState with timer
            game_state, created = GameState.objects.get_or_create(room=self)
            game_state.reset_timer()

    def ensure_player_articles(self, player_id):
        """Ensure player has 15 articles assigned for the game"""
        player_id = str(player_id)
        
        # Skip if player already has articles assigned
        if player_id in self.article_selection and len(self.article_selection[player_id]) == 15:
            return
            
        # Get available articles based on filters
        available_articles = []
        if hasattr(self, 'part') and hasattr(self, 'type') and self.part and self.type:
            # If room has filters, use them
            available_articles = list(Article.objects.filter(
                part=self.part,
                type=self.type
            ).values_list('id', flat=True))
        else:
            # Otherwise get all articles
            available_articles = list(Article.objects.all().values_list('id', flat=True))
            
        # Log the query and results for debugging
        logger.debug(f"Available articles query: {Article.objects.all().query}")
        logger.debug(f"Number of available articles: {len(available_articles)}")
        logger.debug(f"Filters - Part: {getattr(self, 'part', None)}, Type: {getattr(self, 'type', None)}")
        
        if len(available_articles) < 15:
            raise ValueError(f"Not enough articles available. Found {len(available_articles)}, need 15.")
            
        # Randomly select 15 articles if not already assigned
        if player_id not in self.article_selection:
            selected_articles = random.sample(available_articles, 15)
            if not self.article_selection:
                self.article_selection = {}
            self.article_selection[player_id] = selected_articles
            self.save()

    def is_game_completed(self):
        """Check if the game is completed (any player has 15 matches or winner is declared)"""
        # Check if game completion is recorded
        if 'game_completion' in self.selected_cards:
            return True
            
        # Check if any player has 15 matches
        for player_id, selected in self.selected_cards.items():
            if player_id != 'game_completion' and isinstance(selected, list) and len(selected) >= 15:
                return True
                
        return False

    def get_winner(self):
        """Get the winner's username if game is completed"""
        if 'game_completion' in self.selected_cards:
            winner_data = self.selected_cards['game_completion']
            return winner_data.get('winner_username')
        return None

    def check_winner_by_points(self):
        """Check if any player has reached 100 points"""
        winner = None
        max_points = 0
        
        for player in self.players.all():
            points_obj = PlayerPoints.objects.filter(room=self, player=player).first()
            if points_obj and points_obj.points >= 100:
                if points_obj.points > max_points:
                    max_points = points_obj.points
                    winner = player
        
        if winner:
            self.end_game(str(winner.id))
            return True
        return False

    def end_game(self, winning_player_id):
        """End the game and record the winner"""
        try:
            # Mark game as inactive
            self.is_active = False
            
            # Record completion time and winner
            if 'game_completion' not in self.selected_cards:
                self.selected_cards['game_completion'] = {}
            
            # Get winner's username for display
            winner = User.objects.get(id=int(winning_player_id))
            
            completion_time = timezone.now().isoformat()
            self.selected_cards['game_completion'] = {
                'time': completion_time,
                'winner': winning_player_id,
                'winner_username': winner.username,
                'final_points': {}
            }
            
            # Record final points for all players
            for player in self.players.all():
                points_obj = PlayerPoints.objects.filter(room=self, player=player).first()
                points = points_obj.points if points_obj else 0
                self.selected_cards['game_completion']['final_points'][player.username] = points
            
            self.save()
            
            # Update game state
            game_state = GameState.objects.get(room=self)
            game_state.is_active = False
            game_state.round_start_time = None  # Clear the timer
            game_state.save()
            
        except Exception as e:
            print(f"Error ending game: {str(e)}")

class Article(models.Model):
    PART_CHOICES = [
        (5, 'Part 5'),
        (6, 'Part 6'),
    ]
    
    TYPE_CHOICES = [
        ('JUD', 'Judiciary'),
        ('LEG', 'Legislative'),
        ('EXEC', 'Executive'),
    ]
    
    article_number = models.CharField(max_length=10, default='')
    title = models.CharField(max_length=255, default='')
    content = models.TextField(default='')
    part = models.CharField(max_length=50, default='Part 5')
    type = models.CharField(max_length=50, default='Executive')

    def __str__(self):
        return f"Article {self.article_number}: {self.title}"

    class Meta:
        ordering = ['article_number']
        verbose_name = "Constitutional Article"
        verbose_name_plural = "Constitutional Articles"

    def sync_from_constitutional_article(self, constitutional_article):
        """
        Syncs this article with data from a ConstitutionalArticle instance
        """
        self.title = constitutional_article.article_title
        self.content = constitutional_article.simplified_explanation
        self.article_number = constitutional_article.article_number
        self.part = constitutional_article.part
        self.type = constitutional_article.type
        self.save()

    def sync_to_card(self):
        """
        Syncs this article to a corresponding card in the Card model.
        Creates a new card if one doesn't exist, or updates the first one if multiple exist.
        """
        from spinwheel.models import Card  # Import here to avoid circular imports
        
        try:
            # First try to get or create a single card
            cards = Card.objects.filter(article_number=self.article_number)
            
            if cards.exists():
                # If multiple cards exist, update the first one and delete others
                card = cards.first()
                card.title = self.title
                card.content = self.content
                card.save()
                
                # Delete any duplicate cards
                cards.exclude(id=card.id).delete()
                
                return card, False  # False indicates this was an update
            else:
                # Create new card if none exist
                card = Card.objects.create(
                    title=self.title,
                    content=self.content,
                    article_number=self.article_number,
                    rarity="COMMON"  # Default rarity
                )
                return card, True  # True indicates this was a creation
                
        except Exception as e:
            print(f"Error in sync_to_card for article {self.article_number}: {str(e)}")
            return None, False

    @classmethod
    def sync_all_from_constitutional_articles(cls):
        """
        Syncs all articles from ConstitutionalArticle model.
        Returns a tuple of (created_count, updated_count)
        """
        from dbs.models import ConstitutionalArticle  # Import here to avoid circular imports
        
        created = 0
        updated = 0
        
        for const_article in ConstitutionalArticle.objects.all():
            article, was_created = cls.objects.get_or_create(
                article_number=const_article.article_number,
                defaults={
                    'title': const_article.article_title,
                    'content': const_article.simplified_explanation,
                    'part': const_article.part,
                    'type': const_article.type
                }
            )
            
            if not was_created:
                # Update existing article
                article.sync_from_constitutional_article(const_article)
                updated += 1
            else:
                created += 1
        
        return created, updated

    @classmethod
    def sync_all_to_cards(cls):
        """
        Syncs all articles to cards.
        Returns a tuple of (created_count, updated_count)
        """
        created = 0
        updated = 0
        
        for article in cls.objects.all():
            _, was_created = article.sync_to_card()
            if was_created:
                created += 1
            else:
                updated += 1
        
        return created, updated

    def save(self, *args, **kwargs):
        """
        Override save method to automatically sync with Card model
        """
        super().save(*args, **kwargs)
        self.sync_to_card()

class Case(models.Model):
    articles = models.ManyToManyField(Article, related_name='cases')
    title = models.CharField(max_length=255, default='')
    description = models.TextField(default='')
    created_at = models.DateTimeField(default=timezone.now)
    part = models.IntegerField(null=True, blank=True)
    type = models.CharField(max_length=4, null=True, blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_part_and_type()
    
    def update_part_and_type(self):
        """Update the part and type based on associated articles"""
        articles = self.articles.all()
        if articles.exists():
            first_article = articles.first()
            self.part = first_article.part
            self.type = first_article.type
            # Use update to avoid recursive save
            Case.objects.filter(id=self.id).update(
                part=self.part,
                type=self.type
            )

    @classmethod
    def sync_all_parts_and_types(cls):
        """
        Updates all Cases with correct part and type from their articles
        Returns number of cases updated
        """
        updated_count = 0
        for case in cls.objects.all():
            articles = case.articles.all()
            if articles.exists():
                first_article = articles.first()
                if case.part != first_article.part or case.type != first_article.type:
                    Case.objects.filter(id=case.id).update(
                        part=first_article.part,
                        type=first_article.type
                    )
                    updated_count += 1
        return updated_count

class GameState(models.Model):
    room = models.OneToOneField(GameRoom, on_delete=models.CASCADE)
    current_case_index = models.IntegerField(default=0)
    round_start_time = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Game State for Room {self.room.room_id}"

    def reset_timer(self):
        """Reset the timer for a new round"""
        self.round_start_time = timezone.now()
        self.save()

    def get_time_remaining(self):
        """Get remaining time in seconds"""
        # First check if game is completed
        if not self.is_active or self.room.is_game_completed():
            return 0
            
        if not self.round_start_time:
            self.reset_timer()  # Initialize timer if not set
            return 15
            
        elapsed = timezone.now() - self.round_start_time
        remaining = max(0, 15 - int(elapsed.total_seconds()))
        
        # Auto-advance case if time is up
        if remaining == 0 and self.is_active:
            self.advance_case()
            
        return remaining

    def advance_case(self):
        """Advance to the next case and reset timer"""
        if not self.is_active or self.room.is_game_completed():
            return False
            
        if self.room.case_order:
            # Increment the case index
            self.current_case_index = (self.current_case_index + 1) % len(self.room.case_order)
            # Update the room's case index to match
            self.room.current_case_index = self.current_case_index
            self.room.save()
            # Reset the timer
            self.reset_timer()
            return True
        return False

@receiver(post_save, sender=Article)
def auto_sync_article_to_card(sender, instance, created, **kwargs):
    """Signal handler to automatically sync article to card whenever an article is saved"""
    instance.sync_to_card()

@receiver(post_save, sender='dbs.ConstitutionalArticle')
def sync_constitutional_article(sender, instance, created, **kwargs):
    """
    Signal handler to automatically sync ConstitutionalArticle to Article
    whenever a ConstitutionalArticle is saved
    """
    article, _ = Article.objects.get_or_create(article_number=instance.article_number)
    article.sync_from_constitutional_article(instance)

class PlayerPoints(models.Model):
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey('GameRoom', on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0)

    class Meta:
        unique_together = ('player', 'room')
        
    def __str__(self):
        return f"{self.player.username} - {self.points} points in Room {self.room.room_id}"

    def save(self, *args, **kwargs):
        """Override save to sync with platform points"""
        super().save(*args, **kwargs)
        
        # Sync points to platform
        from plat.models import PlayerPlatPoints
        plat_points, _ = PlayerPlatPoints.objects.get_or_create(player=self.player)
        
        # Get total points for this player across all rooms
        total_housie_points = PlayerPoints.objects.filter(
            player=self.player
        ).aggregate(total=models.Sum('points'))['total'] or 0
        
        # Update platform points if different
        if plat_points.housie_points != total_housie_points:
            plat_points.housie_points = total_housie_points
            plat_points.save()