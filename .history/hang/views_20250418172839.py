from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import (
    HangmanGame, PlayerStats, MCQQuestion, FillBlankQuestion,
    MatchPairsQuestion, TrueFalseQuestion, OddOneOutQuestion,
    CategorizeQuestion, WordUnscrambleQuestion
)
from django.db.models import Max, Avg
from django.urls import reverse
import random

def get_random_questions(num_questions=10):
    """Get a random mix of questions from all types."""
    questions = []
    
    # Get all question types
    mcq_questions = list(MCQQuestion.objects.filter(is_active=True))
    fill_questions = list(FillBlankQuestion.objects.filter(is_active=True))
    match_questions = list(MatchPairsQuestion.objects.filter(is_active=True))
    tf_questions = list(TrueFalseQuestion.objects.filter(is_active=True))
    odd_questions = list(OddOneOutQuestion.objects.filter(is_active=True))
    cat_questions = list(CategorizeQuestion.objects.filter(is_active=True))
    scramble_questions = list(WordUnscrambleQuestion.objects.filter(is_active=True))
    
    # Combine all questions
    all_questions = (mcq_questions + fill_questions + match_questions + 
                    tf_questions + odd_questions + cat_questions + scramble_questions)
    
    if not all_questions:
        return []
    
    # Select random questions
    selected_questions = random.sample(all_questions, min(num_questions, len(all_questions)))
    
    # Format questions for frontend
    for question in selected_questions:
        q_dict = {
            'id': question.id,
            'type': question.question_type,
            'question': question.question_text,
            'difficulty': question.difficulty,
        }
        
        if isinstance(question, MCQQuestion):
            q_dict.update({
                'options': question.options,
                'correct_answer': question.correct_answer
            })
        elif isinstance(question, FillBlankQuestion):
            q_dict.update({
                'hint_pattern': question.hint_pattern,
                'answer': question.answer
            })
        elif isinstance(question, MatchPairsQuestion):
            q_dict.update({
                'pairs': question.pairs
            })
        elif isinstance(question, TrueFalseQuestion):
            q_dict.update({
                'correct_answer': question.correct_answer
            })
        elif isinstance(question, OddOneOutQuestion):
            q_dict.update({
                'options': question.options,
                'correct_answer': question.correct_answer,
                'explanation': question.explanation
            })
        elif isinstance(question, CategorizeQuestion):
            q_dict.update({
                'categories': question.categories,
                'items': question.items
            })
        elif isinstance(question, WordUnscrambleQuestion):
            q_dict.update({
                'scrambled_word': question.scrambled_word,
                'correct_word': question.correct_word,
                'hint': question.hint
            })
        
        questions.append(q_dict)
    
    return questions

@login_required
def start_page(request):
    """Renders the start page for the Hangman game."""
    return render(request, 'hang/start_page.html')

@login_required
def game(request):
    """Handles the main game view."""
    # Create a new game instance when the game page is loaded
    game_instance = HangmanGame.objects.create(player=request.user)
    
    # Get player stats for display
    stats, created = PlayerStats.objects.get_or_create(player=request.user)
    
    # Get random questions
    questions = get_random_questions()
    
    start_page_url = reverse('hang:start_page')

    context = {
        'game_id': game_instance.id,
        'player_stats': stats,
        'questions': questions,
        'start_page_url': start_page_url,
    }
    return render(request, 'hang/game.html', context)

@login_required
def end_game(request):
    """Handles the submission of game results."""
    if request.method == 'POST':
        try:
            game_id = request.POST.get('game_id')
            survival_time = int(request.POST.get('survival_time', 0))
            parts_revealed = int(request.POST.get('parts_revealed', 0))
            correct_answers = int(request.POST.get('correct_answers', 0))
            wrong_answers = int(request.POST.get('wrong_answers', 0))
            
            # Get game instance and update its values
            game_instance = HangmanGame.objects.get(id=game_id, player=request.user, is_active=True)
            game_instance.survival_time = survival_time
            game_instance.parts_revealed = parts_revealed
            game_instance.correct_answers = correct_answers
            game_instance.wrong_answers = wrong_answers
            game_instance.end_game()
            
            # Update player stats
            stats, created = PlayerStats.objects.get_or_create(player=request.user)
            stats.games_played += 1
            stats.total_time += survival_time
            stats.best_time = max(stats.best_time, survival_time)
            stats.total_correct_answers += correct_answers
            stats.total_wrong_answers += wrong_answers
            stats.save()
            
            return JsonResponse({'status': 'success'})
        except (HangmanGame.DoesNotExist, ValueError, TypeError) as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def leaderboard(request):
    """Displays the game leaderboard."""
    top_players = PlayerStats.objects.filter(games_played__gt=0).order_by('-best_time')[:10]
    
    player_best_game = HangmanGame.objects.filter(player=request.user, is_active=False).order_by('-survival_time').first()
    
    context = {
        'top_players': top_players,
        'player_best_game': player_best_game
    }
    return render(request, 'hang/leaderboard.html', context)
