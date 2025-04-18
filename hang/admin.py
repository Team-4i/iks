from django.contrib import admin
from .models import (
    HangmanGame, PlayerStats, QuestionCategory,
    MCQQuestion, FillBlankQuestion, MatchPairsQuestion,
    TrueFalseQuestion, OddOneOutQuestion, CategorizeQuestion,
    WordUnscrambleQuestion
)

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

@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

class BaseQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'category', 'difficulty', 'is_active', 'created_at')
    list_filter = ('category', 'difficulty', 'is_active')
    search_fields = ('question_text',)
    ordering = ('-created_at',)

@admin.register(MCQQuestion)
class MCQQuestionAdmin(BaseQuestionAdmin):
    pass

@admin.register(FillBlankQuestion)
class FillBlankQuestionAdmin(BaseQuestionAdmin):
    list_display = BaseQuestionAdmin.list_display + ('hint_pattern',)

@admin.register(MatchPairsQuestion)
class MatchPairsQuestionAdmin(BaseQuestionAdmin):
    pass

@admin.register(TrueFalseQuestion)
class TrueFalseQuestionAdmin(BaseQuestionAdmin):
    list_display = BaseQuestionAdmin.list_display + ('correct_answer',)

@admin.register(OddOneOutQuestion)
class OddOneOutQuestionAdmin(BaseQuestionAdmin):
    pass

@admin.register(CategorizeQuestion)
class CategorizeQuestionAdmin(BaseQuestionAdmin):
    pass

@admin.register(WordUnscrambleQuestion)
class WordUnscrambleQuestionAdmin(BaseQuestionAdmin):
    list_display = BaseQuestionAdmin.list_display + ('scrambled_word', 'correct_word')
