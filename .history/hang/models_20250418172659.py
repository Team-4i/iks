from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import json

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

class QuestionCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Question Categories"

class BaseQuestion(models.Model):
    QUESTION_TYPES = (
        ('MCQ', 'Multiple Choice'),
        ('FILL', 'Fill in the Blank'),
        ('MATCH', 'Match the Pairs'),
        ('TF', 'True/False'),
        ('ODD', 'Odd One Out'),
        ('CAT', 'Categorize'),
        ('SCRAMBLE', 'Word Unscramble'),
    )

    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES)
    question_text = models.TextField()
    difficulty = models.IntegerField(default=1)  # 1: Easy, 2: Medium, 3: Hard
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class MCQQuestion(BaseQuestion):
    options = models.JSONField()  # Store as ["option1", "option2", "option3", "option4"]
    correct_answer = models.CharField(max_length=255)

    def clean(self):
        if not isinstance(self.options, list) or len(self.options) != 4:
            raise ValidationError("Options must be a list of exactly 4 items")
        if self.correct_answer not in self.options:
            raise ValidationError("Correct answer must be one of the options")

class FillBlankQuestion(BaseQuestion):
    answer = models.CharField(max_length=255)
    hint_pattern = models.CharField(max_length=255)  # e.g., "P_th_n" for "Python"

class MatchPairsQuestion(BaseQuestion):
    pairs = models.JSONField()  # Store as {"item1": "match1", "item2": "match2", ...}

    def clean(self):
        if not isinstance(self.pairs, dict) or len(self.pairs) < 2:
            raise ValidationError("Pairs must be a dictionary with at least 2 pairs")

class TrueFalseQuestion(BaseQuestion):
    correct_answer = models.BooleanField()

class OddOneOutQuestion(BaseQuestion):
    options = models.JSONField()  # Store as ["option1", "option2", "option3", "option4"]
    correct_answer = models.CharField(max_length=255)
    explanation = models.TextField()

    def clean(self):
        if not isinstance(self.options, list) or len(self.options) != 4:
            raise ValidationError("Options must be a list of exactly 4 items")
        if self.correct_answer not in self.options:
            raise ValidationError("Correct answer must be one of the options")

class CategorizeQuestion(BaseQuestion):
    categories = models.JSONField()  # Store as ["category1", "category2", ...]
    items = models.JSONField()  # Store as {"item1": "category1", "item2": "category2", ...}

    def clean(self):
        if not isinstance(self.categories, list) or len(self.categories) < 2:
            raise ValidationError("Must have at least 2 categories")
        if not isinstance(self.items, dict) or len(self.items) < 2:
            raise ValidationError("Must have at least 2 items to categorize")
        for category in self.items.values():
            if category not in self.categories:
                raise ValidationError("All items must belong to one of the defined categories")

class WordUnscrambleQuestion(BaseQuestion):
    scrambled_word = models.CharField(max_length=255)
    correct_word = models.CharField(max_length=255)
    hint = models.CharField(max_length=255, blank=True)
