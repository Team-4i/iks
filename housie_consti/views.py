from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import GameRoom, Article, Case, GameState, PlayerPoints
from .forms import ArticleForm, CaseForm
import qrcode
import qrcode.image
import base64
from io import BytesIO
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
import random
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
import json
from base64 import b64encode
import time
import google.generativeai as genai
from django.utils.html import mark_safe
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def calculate_time_remaining(start_time, round_duration=30):
    """
    Calculate remaining time in seconds for the current round
    Args:
        start_time: datetime object when the round started
        round_duration: duration of round in seconds (default 30)
    Returns:
        int: remaining seconds, or 0 if time is up
    """
    if not start_time:
        return 0
        
    elapsed = timezone.now() - start_time
    remaining = round_duration - elapsed.total_seconds()
    
    return max(0, int(remaining))

@login_required
def create_room(request):
    """
    Creates a new game room:
    1. Generates unique room ID
    2. Sets creator as first player
    3. Redirects to room detail page with optional filters
    """
    if request.method == 'POST':
        room = GameRoom.objects.create(creator=request.user)
        room.players.add(request.user)
        
        # Check for filters
        part = request.POST.get('part')
        type = request.POST.get('type')
        
        if part and type:
            # Redirect to filtered room detail
            return redirect('housie_consti:room_detail_filtered', 
                          room_id=room.room_id,
                          part=part,
                          type=type)
        
        return redirect('housie_consti:room_detail', room_id=room.room_id)
    
    return render(request, 'housie_consti/create_room.html')

@login_required
def room_detail(request, room_id, part=None, type=None):
    """
    Shows room joining page with:
    1. Room details and player list
    2. QR code for easy joining
    3. Shareable room link
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Generate appropriate URL based on whether it's filtered or not
    if part and type:
        room_url = request.build_absolute_uri(
            reverse('housie_consti:join_room', args=[room_id]) + f'?part={part}&type={type}'
        )
    else:
        room_url = request.build_absolute_uri(
            reverse('housie_consti:join_room', args=[room_id])
        )
    
    qr.add_data(room_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_code = b64encode(buffer.getvalue()).decode()
    
    context = {
        'room': room,
        'qr_code': qr_code,
        'room_url': room_url,
        'part': part,
        'type': type,
    }
    return render(request, 'housie_consti/room_detail.html', context)

@login_required
def join_room(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    if not room.is_active:
        return redirect('housie_consti:game_board', room_id=room_id)
    
    # Add player if not already in room
    if request.user not in room.players.all():
        room.players.add(request.user)
        # Ensure articles are assigned when player joins
        room.ensure_player_articles(request.user.id)
        room.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Player {request.user.username} joined'
            })
    
    return redirect('housie_consti:room_detail', room_id=room_id)

@login_required
def game_board(request, room_id, part=None, type=None):
    room = get_object_or_404(GameRoom, room_id=room_id)
    if not room.players.filter(id=request.user.id).exists():
        return redirect('housie_consti:join_room', room_id=room_id)
    
    # Ensure player has articles assigned
    room.ensure_player_articles(request.user.id)
    
    context = {
        'room': room,
        'housie_articles': Article.objects.filter(
            id__in=room.article_selection.get(str(request.user.id), [])
        ),
        'part': part,
        'type': type,
    }
    return render(request, 'housie_consti/housie_basic.html', context)

@login_required
def housie_basic(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        
        if not room.game_started:
            return redirect('housie_consti:room_detail', room_id=room_id)
        
        # Ensure player has articles assigned
        room.ensure_player_articles(request.user.id)
        
        # Get player's articles with full article objects
        player_article_ids = room.article_selection.get(str(request.user.id), [])
        housie_articles = Article.objects.filter(id__in=player_article_ids)
        
        # Get initial case data with articles
        current_case = room.get_current_case()
        if current_case:
            case = Case.objects.prefetch_related('articles').get(id=current_case['id'])
            current_case['articles'] = case.articles.all()  # This line loads the articles
        
        # Get previously selected cards for this player
        player_id = str(request.user.id)
        player_selected_cards = room.selected_cards.get(player_id, [])
        
        # Get points for all players
        player_points = {}
        for player in room.players.all():
            points_obj = PlayerPoints.objects.get_or_create(
                room=room,
                player=player,
                defaults={'points': 0}
            )[0]
            player_points[player.username] = points_obj.points
        
        # Create a mapping of article IDs to their selection status
        selected_status = {
            str(article.id): article.id in player_selected_cards 
            for article in housie_articles
        }
        
        context = {
            'room': room,
            'housie_articles': housie_articles,
            'current_case': current_case,
            'selected_cards': player_selected_cards,
            'selected_status': selected_status,
            'player_id': player_id,
            'player_points': player_points,
            'game_completion': room.selected_cards.get('game_completion', {})
        }
        
        return render(request, 'housie_consti/housie_basic.html', context)
        
    except Exception as e:
        print(f"Error in housie_basic: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def manage_content(request):
    articles = Article.objects.all()
    cases = Case.objects.all()
    return render(request, 'housie_consti/manage_content.html', {'articles': articles, 'cases': cases})

@login_required
def manage_articles(request):
    articles = Article.objects.all()
    return render(request, 'housie_consti/manage_articles.html', {'articles': articles})

@login_required
def manage_cases(request):
    cases = Case.objects.all()
    return render(request, 'housie_consti/manage_cases.html', {'cases': cases})

@login_required
def add_article(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('housie_consti:manage_content')
    else:
        form = ArticleForm()
    return render(request, 'housie_consti/article_form.html', {'form': form})

@login_required
def edit_article(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    if request.method == 'POST':
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            return redirect('article_detail', article_id=article.id)
    else:
        form = ArticleForm(instance=article)
    return render(request, 'housie_consti/article_form.html', {'form': form})

@login_required
def delete_article(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    article.delete()
    return redirect('housie_consti:manage_content')

@login_required
def add_case(request):
    if request.method == 'POST':
        form = CaseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('housie_consti:manage_content')
    else:
        form = CaseForm()
    return render(request, 'housie_consti/case_form.html', {'form': form})

@login_required
def edit_case(request, pk):
    case = get_object_or_404(Case, pk=pk)
    if request.method == 'POST':
        form = CaseForm(request.POST, instance=case)
        if form.is_valid():
            case = form.save()
            return redirect('case_detail', pk=case.pk)
    else:
        form = CaseForm(instance=case)
    return render(request, 'housie_consti/case_form.html', {'form': form})
@login_required
def delete_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    case.delete()
    return redirect('housie_consti:manage_content')

@login_required
def get_game_state(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        game_state = get_object_or_404(GameState, room=room)
        
        # Check if game is already completed
        if room.selected_cards.get('game_completion'):
            # Get the winner ID safely
            winner_id = None
            game_completion = room.selected_cards.get('game_completion', {})
            if isinstance(game_completion, dict):
                winner_id = next(iter(game_completion.keys()), None)
            
            if winner_id and winner_id != 'time':  # Skip if winner_id is 'time'
                try:
                    winner = User.objects.get(id=int(winner_id))
                    winner_name = winner.username
                except (ValueError, User.DoesNotExist):
                    winner_name = "Unknown"
            else:
                winner_name = "Game Completed"
            
            # Get final points for all players
            final_points = {
                player.username: PlayerPoints.objects.get_or_create(
                    room=room,
                    player=player,
                    defaults={'points': 0}
                )[0].points
                for player in room.players.all()
            }
            
            return JsonResponse({
                'game_completed': True,
                'winner': winner_name,
                'player_points': final_points,
                'leaderboard_url': reverse('housie_consti:leaderboard', args=[room_id])
            })
        
        # Check if any player has reached 100 points
        for player in room.players.all():
            player_points = PlayerPoints.objects.get_or_create(
                room=room,
                player=player,
                defaults={'points': 0}
            )[0]
            
            if player_points.points >= 100:
                # End game if not already ended
                if not room.selected_cards.get('game_completion'):
                    room.end_game(str(player.id))
                
                # Get final points for all players
                final_points = {
                    p.username: PlayerPoints.objects.get_or_create(
                        room=room,
                        player=p,
                        defaults={'points': 0}
                    )[0].points
                    for p in room.players.all()
                }
                
                return JsonResponse({
                    'game_completed': True,
                    'winner': player.username,
                    'player_points': final_points,
                    'leaderboard_url': reverse('housie_consti:leaderboard', args=[room_id])
                })
        
        # Regular game state updates...
        current_case = room.get_current_case()
        time_remaining = game_state.get_time_remaining()
        
        # Get points for all players
        player_points = {
            player.username: PlayerPoints.objects.get_or_create(
                room=room,
                player=player,
                defaults={'points': 0}
            )[0].points
            for player in room.players.all()
        }
        
        return JsonResponse({
            'current_case': current_case,
            'time_remaining': time_remaining,
            'player_points': player_points,
            'is_active': game_state.is_active
        })
        
    except Exception as e:
        print(f"Error in get_game_state: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def verify_selections(room, selected_indices, player):
    """Verify which selections are correct based on the current case"""
    game_state = GameState.objects.get(room=room)
    current_case = Case.objects.prefetch_related('articles').all()[game_state.current_case_index]
    
    correct_indices = set()
    player_id = str(player.id)
    
    if player_id in room.article_selection:
        player_articles = room.article_selection[player_id]
        correct_article_ids = set(current_case.articles.values_list('id', flat=True))
        
        for idx in selected_indices:
            if idx < len(player_articles):
                article_id = player_articles[idx]
                if article_id not in correct_article_ids:
                    # Record wrong selection
                    room.record_wrong_selection(player.id, article_id, current_case.id)
                else:
                    correct_indices.add(idx)
    
    return correct_indices

@login_required
def check_points(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    room = get_object_or_404(GameRoom, room_id=room_id)
    selected_cells = request.POST.getlist('selected_cells[]')
    
    with transaction.atomic():
        player_points, created = PlayerPoints.objects.get_or_create(
            room=room,
            player=request.user
        )
        
        # Convert selected_cells to a set of indices
        selected_indices = set(int(cell) for cell in selected_cells)
        correct_selections = verify_selections(room, selected_indices, request.user)
        
        # Rest of the check_points function remains the same...

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def check_achievements(request, room_id):
    pass  # Remove this entire function

@login_required
@require_http_methods(["GET"])
def get_recent_achievements(request, room_id):
    pass  # Remove this entire function

@login_required
def check_achievement(request, room_id):
    pass  # Remove this entire function

@login_required
def check_full_housie(request, room_id):
    pass  # Remove this entire function

@require_http_methods(["GET"])
def get_selected_cards(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    player_id = str(request.user.id)
    selected_cards = room.selected_cards.get(player_id, [])
    return JsonResponse({'selected_cards': selected_cards})

@login_required
@require_POST
def mark_card_selected(request, room_id):
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        time_taken = data.get('time_taken', 0)
        
        room = get_object_or_404(GameRoom, room_id=room_id)
        player_id = str(request.user.id)
        
        # Get current case
        current_case = room.get_current_case()
        if not current_case:
            return JsonResponse({'success': False, 'error': 'No active case'})
        
        # Mark card selected and get result
        is_correct = room.mark_card_selected(player_id, article_id)
        
        if is_correct:
            # Get updated points
            player_points = PlayerPoints.objects.get(room=room, player=request.user)
            
            # Check if player has reached 100 points
            if player_points.points >= 100:
                # End game and get final points for all players
                room.end_game(player_id)
                final_points = {
                    player.username: PlayerPoints.objects.get(room=room, player=player).points 
                    for player in room.players.all()
                }
                
                return JsonResponse({
                    'success': True,
                    'points': player_points.points,
                    'game_completed': True,
                    'winner': request.user.username,
                    'final_points': final_points,
                    'leaderboard_url': reverse('housie_consti:leaderboard', args=[room_id])
                })
            
            return JsonResponse({
                'success': True,
                'points': player_points.points
            })
            
        return JsonResponse({'success': False, 'error': 'Incorrect selection'})
        
    except Exception as e:
        print(f"Error in mark_card_selected: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def room_state(request, room_id):
    """API endpoint to get current room state"""
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        
        # Get current timestamp for client-side comparison
        current_time = time.time()
        
        # Get list of players with their status
        players = [{
            'username': player.username,
            'is_creator': player == room.creator
        } for player in room.players.all()]
        
        # Check if game is ready to start (e.g., minimum players joined)
        game_ready = room.players.count() >= 2  # Adjust minimum player count as needed
        
        response_data = {
            'players': players,
            'game_started': room.game_started,
            'game_ready': game_ready,
            'timestamp': current_time
        }
        
        # If game has started, include redirect URL
        if room.game_started:
            response_data['redirect_url'] = reverse('housie_consti:housie_basic', args=[room_id])
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in room_state: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def start_game(request, room_id, part=None, type=None):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Check if user is room creator
    if request.user != room.creator:
        return JsonResponse({'error': 'Only room creator can start the game'}, status=403)
    
    try:
        room.start_game(part=part, type=type)
        redirect_url = reverse('housie_consti:game_board_filtered', kwargs={
            'room_id': room_id,
            'part': part,
            'type': type
        }) if part and type else reverse('housie_consti:game_board', kwargs={'room_id': room_id})
        
        return JsonResponse({
            'success': True,
            'redirect_url': redirect_url
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def check_selected_cards(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    player = request.user
    player_id = str(player.id)

    # Get the selected cards for the current player
    selected_cards = room.selected_cards.get(player_id, [])
    num_selected = len(selected_cards)

    # Initialize points if not already done
    if not room.player_points:
        room.player_points = {}
    if not room.points_awarded:
        room.points_awarded = {'first_five': False, 'full_housie': False}

    achievements = []

    # Check for first 5 cards achievement
    if num_selected >= 5 and not room.points_awarded.get('first_five'):
        room.player_points[player_id] = room.player_points.get(player_id, 0) + 15
        room.points_awarded['first_five'] = True
        achievements.append({
            'type': 'first_five',
            'player': player.username,
            'points': 15
        })

    # Check for full housie (all 15 cards)
    if num_selected == 15 and not room.points_awarded.get('full_housie'):
        room.player_points[player_id] = room.player_points.get(player_id, 0) + 45
        room.points_awarded['full_housie'] = True
        achievements.append({
            'type': 'full_housie',
            'player': player.username,
            'points': 45
        })

    room.save()

    return JsonResponse({
        'success': True,
        'achievements': achievements,
        'player_points': room.player_points.get(player_id, 0)
    })

@login_required
def leaderboard(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        players_data = []
        
        # Get all players in the room with their points
        for player in room.players.all():
            # Get points from PlayerPoints model
            points_obj = PlayerPoints.objects.get_or_create(
                room=room,
                player=player,
                defaults={'points': 0}
            )[0]
            
            # Get selected cards and times for this player
            player_id = str(player.id)
            selected_cards = room.selected_cards.get(player_id, [])
            selection_times = room.selection_times.get(player_id, {})
            
            # Calculate average response time
            times = [float(t.get('time_taken', 0)) for t in selection_times]
            avg_time = sum(times) / len(times) if times else 0
            
            players_data.append({
                'username': player.username,
                'points': points_obj.points,  # Use points from database
                'correct_answers': len(selected_cards),
                'avg_response_time': f"{avg_time:.1f}"
            })
        
        # Sort by points in descending order
        players_data = sorted(players_data, key=lambda x: x['points'], reverse=True)
        
        context = {
            'room': room,
            'players_data': players_data,
            'total_players': room.players.count(),
            'game_duration': (timezone.now() - room.created_at).total_seconds() / 60,
            'total_articles': 15
        }
        
        return render(request, 'housie_consti/leaderboard.html', context)
        
    except Exception as e:
        print(f"Error in leaderboard view: {e}")
        return render(request, 'housie_consti/leaderboard.html', {
            'error_message': str(e)
        })

@login_required
def handle_wrong_selection(request, room_id):
    """API endpoint to record wrong selections"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        case_id = data.get('case_id')
        
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.record_wrong_selection(request.user.id, article_id, case_id)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def record_selection_time(request, room_id):
    """API endpoint to record selection times"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        case_id = data.get('case_id')
        time_taken = data.get('time_taken')
        
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.record_selection_time(request.user.id, article_id, case_id, time_taken)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def check_selection(request, room_id):
    """API endpoint to check if a selection is correct"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        
        if not article_id:
            return JsonResponse({
                'error': 'Missing article_id'
            }, status=400)

        room = get_object_or_404(GameRoom, room_id=room_id)
        
        # Use the same logic as mark_card_selected but without saving
        current_case = room.get_current_case()
        if not current_case:
            return JsonResponse({'correct': False, 'success': True})
            
        case = Case.objects.get(id=current_case['id'])
        is_correct = case.articles.filter(id=article_id).exists()
        
        return JsonResponse({
            'correct': is_correct,
            'success': True
        })
        
    except Exception as e:
        print(f"Error in check_selection: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

@login_required
def game_analysis(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Configure Gemini
    genai.configure(api_key='AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk')
    model = genai.GenerativeModel('gemini-pro')
    
    # Initialize analysis data
    analysis = {
        'players': {},
        'room_stats': {
            'total_players': room.players.count(),
            'game_duration': (timezone.now() - room.created_at).total_seconds() / 60,
        }
    }
    
    # Analyze each player's performance
    for player in room.players.all():
        player_id = str(player.id)
        wrong_selections = room.wrong_selections.get(player_id, [])
        selection_times = room.selection_times.get(player_id, [])
        
        # Calculate average response time properly
        total_time = 0
        num_selections = len(selection_times)
        for selection in selection_times:
            if isinstance(selection, dict) and 'time_taken' in selection:
                total_time += float(selection['time_taken'])
        avg_response_time = total_time / max(num_selections, 1)  # Avoid division by zero
        
        # Generate AI reports for wrong selections
        ai_reports = []
        for wrong_selection in wrong_selections:
            try:
                case = Case.objects.get(id=wrong_selection['case_id'])
                selected_article = Article.objects.get(id=wrong_selection['article_id'])
                correct_articles = case.articles.all()
                
                # Generate AI analysis
                correct_articles_text = ", ".join([art.title for art in correct_articles])
                prompt = f"""
                Analyze this incorrect match in a Supreme Court case study:
                Case: {case.title}
                Selected Article: {selected_article.title}
                Correct Articles: {correct_articles_text}
                
                Please provide:
                1. Brief case description (5 lines)
                2. Why the selected article was incorrect
                3. Why any of the correct articles would have been the right choice
                """
                
                response = model.generate_content(prompt)
                if response.text:
                    ai_reports.append({
                        'case_title': case.title,
                        'selected_article': selected_article.title,
                        'correct_articles': correct_articles_text,
                        'analysis': mark_safe(response.text.replace('\n', '<br>'))
                    })
            except Exception as e:
                print(f"Error generating report: {str(e)}")
                continue
        
        # Add analysis data
        analysis['players'][player.username] = {
            'total_selections': len(room.selected_cards.get(player_id, [])),
            'wrong_selections': len(wrong_selections),
            'accuracy': round(((len(room.selected_cards.get(player_id, [])) - len(wrong_selections)) / 
                            max(len(room.selected_cards.get(player_id, [])), 1)) * 100, 2),
            'avg_response_time': round(avg_response_time, 2),
            'ai_reports': ai_reports
        }

    return render(request, 'housie_consti/game_analysis.html', {
        'room': room,
        'analysis': analysis
    })

@login_required
@require_POST
def select_article(request, room_id):
    try:
        data = json.loads(request.body)
        room = get_object_or_404(GameRoom, room_id=room_id)
        article_id = data.get('article_id')
        time_taken = data.get('time_taken', 15)
        
        # Get current case
        current_case = room.get_current_case()
        if not current_case:
            return JsonResponse({'success': False, 'error': 'No active case'})
        
        case_id = current_case['id']
        player_id = str(request.user.id)
        
        # Check if player already made a selection for this case
        current_case_selections = [
            selection for selection in room.selection_times.get(player_id, [])
            if selection.get('case_id') == case_id
        ]
        
        if current_case_selections:
            return JsonResponse({'success': False, 'error': 'Already selected for this case'})
        
        # Use the mark_card_selected method for consistent logic
        is_correct = room.mark_card_selected(player_id, article_id)
        
        # Record selection time
        room.record_selection_time(player_id, article_id, case_id, time_taken)
        
        # Record wrong selection only if incorrect
        if not is_correct:
            room.record_wrong_selection(player_id, article_id, case_id)
        
        return JsonResponse({'success': is_correct})
        
    except Exception as e:
        print(f"Error in select_article: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def update_points(request, room_id):
    """Update points for a player"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    room = get_object_or_404(GameRoom, room_id=room_id)
    player = request.user
    
    try:
        # Get the player's selected cards
        player_id = str(player.id)
        selected_cards = room.selected_cards.get(player_id, [])
        num_selected = len(selected_cards)
        
        # Get or create player points
        player_points, created = PlayerPoints.objects.get_or_create(
            room=room,
            player=player,
            defaults={'points': 0}
        )
        
        # Update points based on number of selections
        if num_selected >= 5 and player_points.points == 0:  # First 5 cards
            player_points.points += 10
            player_points.save()
            
        return JsonResponse({
            'success': True,
            'points': player_points.points,
            'message': f'Points updated for {player.username}'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
@require_POST
def advance_case(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        game_state = get_object_or_404(GameState, room=room)
        
        if game_state.is_active and not room.is_game_completed():
            case_changed = game_state.advance_case()
            
            if case_changed:
                current_case = room.get_current_case()
                player_points = {}
                for player in room.players.all():
                    points_obj = PlayerPoints.objects.get_or_create(
                        room=room,
                        player=player,
                        defaults={'points': 0}
                    )[0]
                    player_points[str(player.id)] = points_obj.points
                
                return JsonResponse({
                    'success': True,
                    'current_case': current_case,
                    'time_remaining': 15,
                    'case_changed': True,
                    'player_points': player_points,
                    'game_completion': room.selected_cards.get('game_completion', {}),
                    'selected_cards': room.selected_cards
                })
            
            return JsonResponse({
                'success': True,
                'current_case': room.get_current_case(),
                'time_remaining': game_state.get_time_remaining(),
                'case_changed': False,
                'player_points': {},
                'game_completion': room.selected_cards.get('game_completion', {}),
                'selected_cards': room.selected_cards
            })
        
        return JsonResponse({
            'success': False,
            'error': 'Game completed or inactive'
        })
        
    except Exception as e:
        print(f"Error in advance_case: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def housie_intro(request, part=None, type=None):
    """
    View to show the Constitutional Bingo intro/create room page
    """
    context = {
        'part': part,
        'type': type,
        'part_display': dict(Article.PART_CHOICES)[int(part)] if part else None,
        'type_display': dict(Article.TYPE_CHOICES)[type] if type else None
    }
    return render(request, 'housie_consti/create_room.html', context)

def filtered_cases(request, part, type):
    """Get cases filtered by part and type"""
    cases = Case.objects.filter(part=part, type=type).prefetch_related('articles')
    
    cases_data = [{
        'id': case.id,
        'title': case.title,
        'description': case.description,
        'articles': [{
            'id': article.id,
            'article_number': article.article_number,
            'title': article.title
        } for article in case.articles.all()]
    } for case in cases]
    
    return JsonResponse({
        'cases': cases_data,
        'part': part,
        'type': type,
        'part_display': dict(Article.PART_CHOICES)[part],
        'type_display': dict(Article.TYPE_CHOICES)[type]
    })

@login_required
def filtered_game(request):
    """View for filtered game selection page"""
    return render(request, 'housie_consti/filtered_game.html')

@login_required
def preview_filtered_cases(request, part, type):
    """API endpoint to get preview of available cases for selected filters"""
    cases_count = Case.objects.filter(part=part, type=type).count()
    
    return JsonResponse({
        'count': cases_count,
        'part_display': dict(Article.PART_CHOICES)[int(part)],
        'type_display': dict(Article.TYPE_CHOICES)[type],
    })

@login_required
def join_game(request, room_id):
    try:
        # Log the total number of articles
        total_articles = Article.objects.all().count()
        logger.debug(f"Total articles in database: {total_articles}")
        
        # Get the actual query you're using to select articles
        available_articles = Article.objects.all()  # Replace with your actual query
        logger.debug(f"Available articles for game: {available_articles.count()}")
        logger.debug(f"Query used: {available_articles.query}")
        
        # If you're using any filters, log them
        logger.debug(f"First few available articles: {list(available_articles[:5])}")
        
        # Rest of your join game logic
        ...
    except Exception as e:
        logger.error(f"Error joining game: {str(e)}")
        raise
