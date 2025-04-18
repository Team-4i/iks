from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import HangmanGame, PlayerStats
from django.db.models import Max, Avg
from django.urls import reverse

# Create your views here.

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
    
    # Sample MCQs (replace with dynamic loading later)
    mcqs = [
        {"question": "What is the capital of France?", "options": ["Berlin", "Madrid", "Paris", "Rome"], "answer": "Paris"},
        {"question": "Which planet is known as the Red Planet?", "options": ["Earth", "Mars", "Jupiter", "Venus"], "answer": "Mars"},
        {"question": "What is the largest ocean on Earth?", "options": ["Atlantic", "Indian", "Arctic", "Pacific"], "answer": "Pacific"},
        {"question": "Which element has the chemical symbol 'O'?", "options": ["Gold", "Oxygen", "Osmium", "Zinc"], "answer": "Oxygen"},
        {"question": "What is the largest mammal?", "options": ["Elephant", "Giraffe", "Blue Whale", "Polar Bear"], "answer": "Blue Whale"},
        {"question": "Which continent is the Sahara Desert located in?", "options": ["Africa", "Asia", "Australia", "South America"], "answer": "Africa"},
        {"question": "What is the capital of Japan?", "options": ["Beijing", "Seoul", "Tokyo", "Bangkok"], "answer": "Tokyo"},
        {"question": "In which sport would you perform a slam dunk?", "options": ["Tennis", "Basketball", "Soccer", "Golf"], "answer": "Basketball"},
        {"question": "What is the smallest prime number?", "options": ["0", "1", "2", "3"], "answer": "2"},
        {"question": "Who wrote 'Romeo and Juliet'?", "options": ["Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain"], "answer": "William Shakespeare"},
    ]
    
    start_page_url = reverse('hang:start_page')

    context = {
        'game_id': game_instance.id,
        'player_stats': stats,
        'mcqs': mcqs,
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
