from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class HangmanGame(models.Model):
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    survival_time = models.IntegerField(default=0)  # Time in seconds
    is_active = models.BooleanField(default=True)
    parts_revealed = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)  # Track correct answers
    wrong_answers = models.IntegerField(default=0)    # Track wrong answers
    
    class Meta:
        ordering = ['-survival_time']
    
    def end_game(self):
        self.end_time = timezone.now()
        self.is_active = False
        self.survival_time = (self.end_time - self.start_time).seconds
        self.save()

class PlayerStats(models.Model):
    player = models.OneToOneField(User, on_delete=models.CASCADE)
    games_played = models.IntegerField(default=0)
    best_time = models.IntegerField(default=0)
    total_time = models.IntegerField(default=0)
    total_correct_answers = models.IntegerField(default=0)  # Total correct answers across all games
    total_wrong_answers = models.IntegerField(default=0)    # Total wrong answers across all games
    
    class Meta:
        ordering = ['-best_time']
