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
import json
from django.core.serializers.json import DjangoJSONEncoder

def get_random_questions(num_questions=10, allowed_types=None):
    """Get a random mix of questions from all types, optionally filtered."""
    questions = []
    
    all_question_types = {
        'MCQ': MCQQuestion,
        'FILL': FillBlankQuestion,
        'MATCH': MatchPairsQuestion,
        'TF': TrueFalseQuestion,
        'ODD': OddOneOutQuestion,
        'CAT': CategorizeQuestion,
        'SCRAMBLE': WordUnscrambleQuestion,
    }

    # Determine which types to fetch
    types_to_fetch = allowed_types if allowed_types else all_question_types.keys()

    # Fetch questions based on allowed types
    all_questions = []
    for q_type in types_to_fetch:
        if q_type in all_question_types:
            model = all_question_types[q_type]
            all_questions.extend(list(model.objects.filter(is_active=True)))
    
    if not all_questions:
        return []
    
    # Select random questions from the fetched pool
    selected_questions = random.sample(all_questions, min(num_questions, len(all_questions)))
    
    # Format questions for frontend
    for question in selected_questions:
        q_dict = {
            'id': question.id,
            'type': question.question_type,
            'question': question.question_text,
            'difficulty': question.difficulty,
        }
        
        # Dynamically add specific fields based on type
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
                'correct_answer': 'true' if question.correct_answer else 'false' 
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
    game_instance = HangmanGame.objects.create(player=request.user)
    stats, created = PlayerStats.objects.get_or_create(player=request.user)
    
    # Get allowed question types from URL parameter
    allowed_types_str = request.GET.get('types', '')
    allowed_types = [t.strip().upper() for t in allowed_types_str.split(',') if t.strip()]
    if not allowed_types: # If empty or not provided, allow all
        allowed_types = None 
        
    questions = get_random_questions(allowed_types=allowed_types)
    
    start_page_url = reverse('hang:start_page')

    context = {
        'game_id': game_instance.id,
        'player_stats': stats,
        'questions_json': json.dumps(questions, cls=DjangoJSONEncoder),
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
