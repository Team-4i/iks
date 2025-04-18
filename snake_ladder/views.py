from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Cell, GameRoom, PlayerPosition, CellHistory, User, PlayerOverallPoints, CellContent, CellBookmark, GameFact
from plat.models import PlayerPlatPoints
import qrcode
import qrcode.image.svg
from io import BytesIO
from base64 import b64encode
import time
from django.http import JsonResponse
import google.generativeai as genai
import json
import random
from django.db.models import Count, Avg, Sum
from django.db.models import Q
from datetime import datetime
import os
from django.utils.timezone import now
import math
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction

def generate_dice_roll():
    """
    Creates a fair dice roll (1-6) using microsecond timestamp
    Prevents cheating by using server-side generation
    Returns both roll value and timestamp for verification
    """
    timestamp = int(time.time() * 1000000)
    dice_roll = ((timestamp % 6) + 1)  # 1 to 6
    return dice_roll, timestamp

@login_required
def game_board(request, room_id):
    """
    Main game view that handles:
    1. Showing winner page if game is complete
    2. Generating 10x10 snake & ladder board
    3. Managing player positions and turns
    4. Processing dice rolls and player movements
    5. Showing educational content for current cell
    6. Updating game state after each move
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Ensure cells exist
    initialize_cells()
    
    # If game is over, sync points with platform
    if room.winner:
        try:
            # Get player's platform points
            player_points = PlayerPlatPoints.objects.get(player=request.user)
            # Update snake ladder points from game points
            game_points = room.points.get(str(request.user.id), 0)
            
            print(f"[DEBUG] Syncing game points to platform - User: {request.user.username}, Points: {game_points}")
            
            # Update platform points for snake ladder
            player_points.update_points(game_points, 'SNAKE_LADDER')
            
        except PlayerPlatPoints.DoesNotExist:
            print(f"[DEBUG] No platform points found for user: {request.user.username}")
    
    # If game is just starting
    if not room.current_content_part:  # Check if content type not set yet
        # Set default content type (no longer dependent on platform)
        room.set_game_content_type(part=5, type='JUD')
    
    dice_roll = None  # Initialize dice_roll at the start
    
    if request.user not in room.players.all():
        return redirect('snake_ladder:join_room', room_id=room_id)
    
    if request.method == 'POST' and request.POST.get('roll'):
        if room.current_turn == request.user:
            dice_roll, timestamp = generate_dice_roll()
            player_position = PlayerPosition.objects.get(room=room, player=request.user)
            new_position = player_position.position + dice_roll
            
            # Update position and check for winner
            is_winner = False
            if new_position == 100:
                is_winner = True
                new_position = 100
            elif new_position > 100:
                new_position = player_position.position
            
            # Update position and history
            player_position.position = new_position
            player_position.save()
            
            current_cell = Cell.objects.get(number=new_position)
            CellHistory.objects.create(
                player=request.user,
                room=room,
                cell=current_cell,
                dice_roll=dice_roll
            )
            
            # Update room state if winner
            if is_winner:
                room.winner = request.user
                room.is_active = False
                room.update_points(request.user.id, 40)
                room.save()
                return JsonResponse({
                    'dice_roll': dice_roll,
                    'new_position': new_position,
                    'timestamp': timestamp,
                    'winner': request.user.username
                })
            
            # Update turn
            player_list = list(room.players.all())
            current_index = player_list.index(request.user)
            next_index = (current_index + 1) % len(player_list)
            room.current_turn = player_list[next_index]
            room.save()
            
            return JsonResponse({
                'dice_roll': dice_roll,
                'new_position': new_position,
                'timestamp': timestamp
            })
    
    # If game is already won, show winner page with statistics
    if room.winner:
        # Calculate game statistics
        total_moves = CellHistory.objects.filter(room=room).count()
        correct_answers = CellHistory.objects.filter(
            room=room, 
            answer_correct=True
        ).count()
        
        # Get time played (in minutes)
        first_move = CellHistory.objects.filter(room=room).order_by('visited_at').first()
        last_move = CellHistory.objects.filter(room=room).order_by('-visited_at').first()
        time_played = "N/A"
        if first_move and last_move:
            minutes = (last_move.visited_at - first_move.visited_at).total_seconds() / 60
            time_played = f"{int(minutes)} minutes"
        
        # Get final positions
        positions = {}
        for player in room.players.all():
            position = PlayerPosition.objects.get(room=room, player=player)
            positions[player.id] = position.position
        
        player_stats = {}
        for player in room.players.all():
            player_moves = CellHistory.objects.filter(room=room, player=player).count()
            player_correct = CellHistory.objects.filter(
                room=room, 
                player=player,
                answer_correct=True
            ).count()
            
            # Get player's first and last move
            player_first_move = CellHistory.objects.filter(room=room, player=player).order_by('visited_at').first()
            player_last_move = CellHistory.objects.filter(room=room, player=player).order_by('-visited_at').first()
            
            player_time = "N/A"
            if player_first_move and player_last_move:
                minutes = (player_last_move.visited_at - player_first_move.visited_at).total_seconds() / 60
                player_time = f"{int(minutes)} minutes"
            
            player_stats[player.id] = {
                'total_moves': player_moves,
                'correct_answers': player_correct,
                'time_played': player_time,
                'accuracy': f"{(player_correct / player_moves * 100):.1f}%" if player_moves > 0 else "0%"
            }
        
        return render(request, 'winner.html', {
            'room': room,
            'winner': room.winner,
            'total_moves': total_moves,
            'correct_answers': correct_answers,
            'time_played': time_played,
            'players': room.players.all(),
            'positions': positions,
            'player_stats': player_stats
        })
    
    # Get cells first
    cells = Cell.objects.all().order_by('number')
    cells_dict = {cell.number: cell for cell in cells}
    
    # Board generation - Updated to start from bottom left
    board = []
    numbers = list(range(1, 101))  # Start from 1 to 100
    for i in range(9, -1, -1):  # Start from bottom row (9) to top row (0)
        row = numbers[i * 10:(i + 1) * 10]
        if i % 2 == 1:  # Alternate rows go right to left
            row = list(reversed(row))
        board.append(row)
    
    # Get player positions
    positions = {}
    for player in room.players.all():
        position, _ = PlayerPosition.objects.get_or_create(
            room=room, 
            player=player,
            defaults={'position': 1}
        )
        positions[player.id] = position.position
    
    # Create visible cells
    visible_cells = {}
    if request.user.id in positions:
        current_position = positions[request.user.id]
        cell = cells_dict.get(current_position)
        if cell and cell.current_content:  # Check for current_content
            current_time = time.time()
            visible_cells[current_position] = {
                'content': cell.current_content.content,  # Get content from current_content
                'topic': cell.current_content.topic if cell.current_content else None,
                'timestamp': current_time,
                'expires': current_time + 30
            }
    
    # Initialize dice_roll as None
    last_dice_roll = None
    
    # Handle dice roll
    if request.method == 'POST' and request.POST.get('roll'):
        if room.current_turn == request.user:
            dice_roll, timestamp = generate_dice_roll()
            player_position = PlayerPosition.objects.get(room=room, player=request.user)
            new_position = player_position.position + dice_roll
            
            # Update position logic
            if new_position == 100:
                room.winner = request.user
                room.is_active = False
                room.update_points(request.user.id, 40)
                room.save()
                return JsonResponse({
                    'redirect': True, 
                    'winner': room.winner.username,
                    'points': room.points.get(str(request.user.id), 0)
                })
            elif new_position > 100:
                new_position = player_position.position
            
            # Update position and history
            current_cell = Cell.objects.get(number=new_position)
            player_position.position = new_position
            player_position.save()
            
            CellHistory.objects.create(
                player=request.user,
                room=room,
                cell=current_cell,
                dice_roll=dice_roll
            )
            
            # Update turn
            player_list = list(room.players.all())
            current_index = player_list.index(request.user)
            next_index = (current_index + 1) % len(player_list)
            room.current_turn = player_list[next_index]
            room.save()
            
            # Return JSON response with dice roll
            return JsonResponse({
                'dice_roll': dice_roll,
                'new_position': new_position,
                'timestamp': timestamp
            })
    
    context = {
        'room': room,
        'board': board,
        'cells': cells_dict,
        'players': room.players.all(),
        'current_turn': room.current_turn,
        'positions': positions,
        'visible_cells': visible_cells,
        'dice_roll': dice_roll,
        'last_dice_roll': last_dice_roll,  # Add to context
    }
    
    return render(request, 'game_board.html', context)

@login_required
def create_room(request):
    """Creates a new game room with dynamic content support"""
    # Get parameters for content selection
    topic_group_id = request.GET.get('topic_group_id')
    summary_id = request.GET.get('summary_id')
    checkpoint_part = request.GET.get('checkpoint_part')
    checkpoint_type = request.GET.get('checkpoint_type')
    auto_start = request.GET.get('auto_start', 'false').lower() == 'true'
    
    # Create new room
    room = GameRoom.objects.create(
        creator=request.user
    )
    room.players.add(request.user)
    room.current_turn = request.user
    room.save()
    
    # Store content information in session
    content_source = {}
    
    # Check if we have topic-based parameters
    if topic_group_id and summary_id:
        try:
            from dynamicDB.models import MainTopic, SubTopic
            # Try to get the topic group and summary topic
            topic_group = MainTopic.objects.get(pk=topic_group_id)
            summary_topic = SubTopic.objects.get(pk=summary_id, topic_group=topic_group)
            
            # Store in session for later use
            request.session['topic_group_id'] = topic_group_id
            request.session['summary_id'] = summary_id
            request.session['topic_group_title'] = topic_group.title
            request.session['summary_topic_title'] = summary_topic.title
            request.session['summary_topic_description'] = summary_topic.description
            request.session['using_dynamic_content'] = True
            
            # Create mapping to part/type for compatibility with existing code
            # Determine part/type equivalent based on position
            try:
                from dynamicDB.models import ActiveTopicGroups
                active_groups = ActiveTopicGroups.get_active_groups()
                active_group_ids = [group.topic_group.id for group in active_groups]
                
                if int(topic_group_id) in active_group_ids:
                    # Find position in active groups (0 = Part 5, 1 = Part 6)
                    group_index = active_group_ids.index(int(topic_group_id))
                    part = 5 if group_index == 0 else 6
                    
                    # Get all summary topics for this group
                    summary_topics = list(SubTopic.objects.filter(topic_group=topic_group).order_by('order'))
                    if int(summary_id) in [topic.id for topic in summary_topics]:
                        topic_index = [topic.id for topic in summary_topics].index(int(summary_id))
                        # Map index to type (0 = JUD, 1 = LEG, 2+ = EXEC)
                        if topic_index == 0:
                            type_code = 'JUD'
                        elif topic_index == 1:
                            type_code = 'LEG'
                        else:
                            type_code = 'EXEC'
                        
                        # Store legacy part/type for backward compatibility
                        request.session['checkpoint_part'] = part
                        request.session['checkpoint_type'] = type_code
                        
                        # Set room's content type
                        room.current_content_part = part
                        room.current_content_type = type_code
                        room.save()
                        
                        # Set content_source for messages
                        content_source = {
                            'title': summary_topic.title,
                            'is_dynamic': True
                        }
            except Exception as e:
                print(f"Error mapping to part/type: {e}")
                
            messages.success(request, f"Room created with content from '{summary_topic.title}'")
            
        except Exception as e:
            print(f"Error loading dynamic content: {e}")
            messages.warning(request, "Could not load the specified dynamic content. Using default content.")
            
    # Check for traditional part/type parameters if no topic-based content
    elif checkpoint_part and checkpoint_type:
        try:
            part = int(checkpoint_part)
            type_code = checkpoint_type
            
            # Store in session
            request.session['checkpoint_part'] = part
            request.session['checkpoint_type'] = type_code
            request.session['using_dynamic_content'] = False
            
            # Set room's content type
            room.current_content_part = part
            room.current_content_type = type_code
            room.save()
            
            # Get display name for the type
            type_names = {
                'JUD': 'Judiciary',
                'LEG': 'Legislative',
                'EXEC': 'Executive'
            }
            
            # Set content_source for messages
            content_source = {
                'title': f"Part {part} {type_names.get(type_code, type_code)}",
                'is_dynamic': False
            }
            
            messages.success(request, f"Room created with content from Part {part} {type_names.get(type_code, type_code)}")
            
        except Exception as e:
            print(f"Error setting part/type: {e}")
            messages.warning(request, "Could not set the specified part and type. Using default content.")
    
    # If no specific content source, use active topic groups if available
    if not content_source:
        try:
            from dynamicDB.models import ActiveTopicGroups, SubTopic
            active_groups = ActiveTopicGroups.get_active_groups()
            
            if active_groups.exists():
                # Use the first active topic group
                topic_group = active_groups.first().topic_group
                
                # Look for summary topics in this group
                summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
                
                if summary_topics.exists():
                    # Use the first summary topic
                    summary_topic = summary_topics.first()
                    
                    # Store in session
                    request.session['topic_group_id'] = topic_group.id
                    request.session['summary_id'] = summary_topic.id
                    request.session['topic_group_title'] = topic_group.title
                    request.session['summary_topic_title'] = summary_topic.title
                    request.session['summary_topic_description'] = summary_topic.description
                    request.session['using_dynamic_content'] = True
                    
                    # Map to part/type (first topic group = part 5, first summary = JUD)
                    request.session['checkpoint_part'] = 5
                    request.session['checkpoint_type'] = 'JUD'
                    
                    # Set room's content type
                    room.current_content_part = 5
                    room.current_content_type = 'JUD'
                    room.save()
                    
                    messages.success(request, f"Room created with content from active topic '{summary_topic.title}'")
                    
                    # Set content_source
                    content_source = {
                        'title': summary_topic.title,
                        'is_dynamic': True
                    }
            
            # If still no content_source, fall back to default
            if not content_source:
                # Set default part/type
                room.current_content_part = 5
                room.current_content_type = 'JUD'
                room.save()
                
                # Store in session
                request.session['checkpoint_part'] = 5
                request.session['checkpoint_type'] = 'JUD'
                request.session['using_dynamic_content'] = False
                
                messages.info(request, "Using default content (Part 5 Judiciary).")
                
                # Set content_source
                content_source = {
                    'title': "Part 5 Judiciary",
                    'is_dynamic': False
                }
                
        except Exception as e:
            print(f"Error finding active content: {e}")
            # Set default part/type
            room.current_content_part = 5
            room.current_content_type = 'JUD'
            room.save()
            
            # Store in session
            request.session['checkpoint_part'] = 5
            request.session['checkpoint_type'] = 'JUD'
            request.session['using_dynamic_content'] = False
            
            messages.info(request, "Using default content (Part 5 Judiciary).")
    
    # Automatically start the game if requested
    if auto_start:
        return start_game(request, room.room_id)
    
    # Return the created room's detail page
    return redirect('snake_ladder:room_detail', room_id=room.room_id)

@login_required
def room_detail(request, room_id):
    """View a game room and its details"""
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Get summary topic info from session
    summary_id = request.session.get('summary_id')
    summary_topic_title = request.session.get('summary_topic_title')
    summary_topic_description = request.session.get('summary_topic_description')
    
    # If we don't have summary info in session but room has players, try to get it from the first player's session
    if not summary_topic_title and room.players.exists():
        try:
            from django.contrib.sessions.models import Session
            from django.contrib.sessions.backends.db import SessionStore
            from dynamicDB.models import SubTopic
            
            # Try to get summary topic details if we have the ID
            if summary_id:
                summary_topic = SubTopic.objects.get(pk=summary_id)
                summary_topic_title = summary_topic.title
                summary_topic_description = summary_topic.description
        except Exception as e:
            print(f"Error retrieving summary topic info: {e}")
    
    # Check if game is started
    is_started = not room.is_active and room.current_turn is not None
    
    context = {
        'room': room,
        'is_creator': request.user == room.creator,
        'is_started': is_started,
        'player_count': room.players.count(),
        'player_colors': room.get_player_color(),
        'summary_id': summary_id,
        'summary_topic_title': summary_topic_title,
        'summary_topic_description': summary_topic_description,
    }
    
    return render(request, 'snake_ladder/room_detail.html', context)

@login_required
def join_room(request, room_id):
    """
    Handles new player joining:
    1. Adds player to room if not already in
    2. Redirects to room detail page
    3. Triggers immediate update for all clients
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Don't allow joining if game has started
    if not room.is_active:
        return redirect('snake_ladder:game_board', room_id=room_id)
    
    # Add player if not already in room
    if request.user not in room.players.all():
        room.players.add(request.user)
        room.save()  # Force a save to trigger update
        
        # Return JSON response for AJAX calls
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Player {request.user.username} joined'
            })
    
    return redirect('snake_ladder:room_detail', room_id=room_id)

@login_required
def game_state(request, room_id):
    """
    Real-time game state API that returns:
    1. Current player positions
    2. Whose turn it is
    3. Visible cell contents
    4. Player colors and data
    5. Game over status
    Used for continuous game updates
    """
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.refresh_from_db()
        
        # Get all player positions
        positions = {
            position.player_id: position.position 
            for position in PlayerPosition.objects.filter(room=room)
        }
        
        # Check for winner
        for player_id, position in positions.items():
            if position >= 100 and not room.winner:
                winner = get_object_or_404(User, id=player_id)
                room.winner = winner
                # Add 40 points for winning
                room.update_points(winner.id, 40)
                
                # Update overall points for all players in the room
                for player in room.players.all():
                    player_points = room.points.get(str(player.id), 0)
                    overall_points, _ = PlayerOverallPoints.objects.get_or_create(player=player)
                    overall_points.total_points += player_points
                    overall_points.save()
                
                room.is_active = False
                room.save()
                
                return JsonResponse({
                    'winner': winner.username,
                    'points': room.points,
                    'redirect_url': reverse('snake_ladder:game_over', args=[room_id])
                })
        
        # Get the latest dice roll with a more precise timestamp
        latest_roll = CellHistory.objects.filter(
            room=room,
            dice_roll__isnull=False
        ).select_related('player').order_by('-visited_at').first()

        # Add dice roll information with roll ID to prevent duplicates
        dice_info = None
        if latest_roll:
            dice_info = {
                'value': latest_roll.dice_roll,
                'timestamp': latest_roll.visited_at.timestamp(),
                'player_name': latest_roll.player.username,
                'player_id': latest_roll.player.id,
                'roll_id': f"{latest_roll.id}_{latest_roll.visited_at.timestamp()}"  # Unique roll ID
            }

        # Check if game is over
        if room.winner:
            return JsonResponse({
                'redirect_url': reverse('snake_ladder:game_board', args=[room_id])
            })
        
        # If no current turn is set, set it to the first player
        if not room.current_turn and room.players.exists():
            room.current_turn = room.players.first()
            room.save()
        
        positions = {}
        visible_cells = {}
        player_colors = room.get_player_color()
        players_data = []
        
        # Get fresh position data
        for player in room.players.all():
            position = PlayerPosition.objects.get(room=room, player=player).position
            positions[player.id] = position
            
            # Show cell content for current user's position
            if player.id == request.user.id:
                cell = Cell.objects.select_related('current_content').filter(number=position).first()
                if cell and cell.current_content:  # Check for current_content
                    force_display = CellHistory.objects.filter(
                        room=room,
                        player=request.user,
                        cell__number=position,
                        answer_correct=False
                    ).exists()
                    
                    visible_cells[position] = {
                        'content': cell.current_content.content,
                        'topic': cell.current_content.topic,
                        'force_display': force_display
                    }
            
            # Add player data including color
            color = player_colors.get(player, ('gray-500', 'Gray'))[0]
            players_data.append({
                'id': player.id,
                'username': player.username,
                'color': color,
                'is_current_turn': player.id == room.current_turn.id if room.current_turn else False
            })

        return JsonResponse({
            'game_over': False,
            'current_turn': room.current_turn.id if room.current_turn else None,
            'current_turn_username': room.current_turn.username if room.current_turn else '',
            'positions': positions,
            'visible_cells': visible_cells,
            'players': players_data,
            'current_user_id': request.user.id,
            'latest_dice': dice_info,
            'points': room.points,  # Add this line
            'timestamp': time.time()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def home(request):
    """Homepage for the Snake & Ladder game with room creation options"""
    # Get active rooms
    active_rooms = GameRoom.objects.filter(is_active=True).order_by('-created_at')
    
    # Get active summary topics
    summary_topics = []
    first_summary_id = None
    try:
        from dynamicDB.models import SubTopic, ActiveTopicGroups
        active_groups = ActiveTopicGroups.get_active_groups()
        
        for group in active_groups:
            topic_group = group.topic_group
            group_summary_topics = SubTopic.objects.filter(topic_group=topic_group)
            
            for topic in group_summary_topics:
                main_topics_count = topic.main_topics.count()
                summary_topics.append({
                    'id': topic.id,
                    'title': topic.title,
                    'description': topic.description[:100] + '...' if len(topic.description) > 100 else topic.description,
                    'main_topics_count': main_topics_count,
                    'topic_group': topic_group.title
                })
                
                # Remember the first summary topic ID
                if first_summary_id is None:
                    first_summary_id = topic.id
    except Exception as e:
        print(f"Error fetching summary topics: {e}")
    
    context = {
        'active_rooms': active_rooms,
        'summary_topics': summary_topics,
        'first_summary_id': first_summary_id
    }
    
    return render(request, 'snake_ladder/home.html', context)

def verify_board(request):
    """
    Validates game board setup:
    1. Counts total cells
    2. Identifies special cells (snakes/ladders)
    3. Calculates distribution percentages
    Used for admin verification
    """
    cells = Cell.objects.all().order_by('number')
    snake_ladder_cells = cells.filter(cell_type='SNAKE_LADDER').values_list('number', flat=True)
    return JsonResponse({
        'total_cells': cells.count(),
        'snake_ladder_cells': list(snake_ladder_cells),
        'percentage': (len(snake_ladder_cells) / cells.count()) * 100
    })

@login_required
def generate_mcq(request, room_id):
    """
    Creates MCQ questions when player lands on special cell:
    1. Gets cell's educational content
    2. Uses AI to generate relevant question
    3. Creates 4 options with 1 correct answer
    4. Returns question data in JSON format
    """
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        player_position = PlayerPosition.objects.get(room=room, player=request.user)
        current_position = player_position.position

        # Get only the last 10 visited normal cells
        visited_cells = CellHistory.objects.filter(
            room=room,
            player=request.user,
            cell__cell_type='NORMAL'
        ).select_related('cell__current_content').order_by('-visited_at')[:10]

        if not visited_cells:
            # If no cells visited yet, use current cell as fallback
            source_cell = Cell.objects.select_related('current_content').get(number=current_position)
        else:
            # Randomly select one cell from the last 10 visited cells
            source_cell = random.choice(visited_cells).cell

        # Use content from current_content
        content_for_question = source_cell.current_content.content if source_cell.current_content else "Default content"
        topic_for_question = source_cell.current_content.topic if source_cell.current_content else "IKS"

        print(f"[DEBUG] Generating MCQ for content: {content_for_question[:100]}...")
        print(f"[DEBUG] Topic: {topic_for_question}")

        # Generate MCQ using the selected cell's content
        genai.configure(api_key='AIzaSyA8DaPlDtUTyzwjo8M6aOwFcfGDLU7itJg')
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""Based on this fact about Indian Constitution:
        {content_for_question}
        Create a multiple choice question testing their knowledge of this specific fact.
        Return only valid JSON in this exact format:
        {{"question": "your question", "options": ["A) option1", "B) option2", "C) option3", "D) option4"], "correct": "A"}}"""
        
        print(f"[DEBUG] Sending prompt to Gemini API")
        response = model.generate_content(prompt)
        
        print(f"[DEBUG] Received response from Gemini API")
        print(f"[DEBUG] Response text: {response.text}")
        
        try:
            print(f"[DEBUG] Attempting to parse JSON from response")
            
            # Clean the response text to handle markdown code blocks
            response_text = response.text.strip()
            if response_text.startswith("```json") and response_text.endswith("```"):
                # Extract JSON from markdown code block
                response_text = response_text[7:-3].strip()  # Remove ```json and ``` markers
                print(f"[DEBUG] Extracted JSON from markdown: {response_text}")
            
            data = json.loads(response_text)
            print(f"[DEBUG] JSON parsed successfully: {data}")
            
            if not all(key in data for key in ['question', 'options', 'correct']):
                print(f"[DEBUG] Missing required keys in JSON response")
                raise ValueError("Invalid response format")
            
            data['source_cell'] = source_cell.number
            data['topic_category'] = topic_for_question
            print(f"[DEBUG] Returning valid question data")
            return JsonResponse(data)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON decode error: {str(e)}")
            print(f"[DEBUG] Falling back to default question")
            return JsonResponse({
                "source_cell": source_cell.number,
                "question": "What type of democracy is India?",
                "options": [
                    "A) Parliamentary Democracy",
                    "B) Presidential Democracy",
                    "C) Direct Democracy",
                    "D) Authoritarian Democracy"
                ],
                "correct": "A",
                "topic_category": topic_for_question
            })
    except Exception as e:
        print(f"[DEBUG] Error in generate_mcq: {str(e)}")
        return JsonResponse({"error": str(e)})

@login_required
def answer_mcq(request, room_id):
    try:
        data = json.loads(request.body)
        room = get_object_or_404(GameRoom, room_id=room_id)
        player_position = PlayerPosition.objects.get(room=room, player=request.user)
        current_position = player_position.position
        
        # Extract data from request
        is_correct = data.get('correct', False)
        time_taken = data.get('time_taken', 10)
        source_cell = data.get('source_cell')
        
        # Add points for correct answer
        if is_correct:
            room.update_points(request.user.id, 10)  # Add 10 points for correct answer
        
        # Create cell history with source cell
        CellHistory.objects.create(
            player=request.user,
            room=room,
            cell=Cell.objects.get(number=current_position),
            question_text=data.get('question', ''),
            selected_answer=data.get('selected_option', ''),
            correct_answer=data.get('correct_option', ''),
            answer_correct=is_correct,
            time_to_answer=time_taken,
            topic_category=data.get('topic_category', 'Constitutional Law'),
            options=json.dumps(data.get('all_options', [])),
            source_cell=source_cell,
            difficulty_level='MEDIUM',
            visited_at=now(),
            cumulative_score=calculate_score(is_correct, time_taken)
        )
        
        # Calculate movement
        if is_correct:
            # Calculate move amount based on response time
            move_amount = min(
                math.ceil(3 + 20 / (time_taken + 1)),
                12  # MAX_MOVE
            )
            new_position = min(current_position + move_amount, 100)
            
            # Check if new position is a snake/ladder cell
            try:
                current_cell = Cell.objects.get(number=new_position)
                if current_cell.cell_type == 'SNAKE_LADDER':
                    new_position = new_position + 1 if new_position < 100 else new_position - 1
            except Cell.DoesNotExist:
                pass
        else:
            move_amount = source_cell - current_position
            new_position = max(source_cell, 1)
        
        # Update player position
        player_position.position = new_position
        player_position.save()
        
        # Get content for new position
        try:
            new_cell = Cell.objects.get(number=new_position)
            cell_content = new_cell.current_content.content if new_cell.current_content else None
        except Cell.DoesNotExist:
            cell_content = None
        
        return JsonResponse({
            'success': True,
            'move_amount': move_amount,
            'new_position': new_position,
            'cell_content': cell_content,
            'points_earned': 10 if is_correct else 0,
            'total_points': room.points.get(str(request.user.id), 0)  # Include total points
        })
        
    except Exception as e:
        print(f"Error in answer_mcq: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

def generate_topic_title(content):
    """Generate a 2-word topic title for cell content using Gemini"""
    try:
        genai.configure(api_key='AIzaSyA8GHU0QhwXkgCXEBYnost56YOPmsd2pPs')
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Generate a 2-word topic title for this educational content. The title should be specific and descriptive.
        Keep it exactly 2 words, with proper capitalization. Example: "Constitutional Rights" or "Criminal Law"

        Content: {content}
        
        Response format: Just the 2-word title, nothing else.
        """
        
        response = model.generate_content(prompt)
        title = response.text.strip()
        
        # Validate it's 2 words
        if len(title.split()) == 2:
            return title
        return None
    except:
        return None

def prepare_comparative_time_graph(room, current_user):
    """Prepares data for comparing question response times between players"""
    players = room.players.all()
    
    # Predefined colors for better visibility
    color_palette = [
        {'border': 'rgb(59, 130, 246)', 'background': 'rgba(59, 130, 246, 0.1)'},  # Blue
        {'border': 'rgb(16, 185, 129)', 'background': 'rgba(16, 185, 129, 0.1)'},  # Green
        {'border': 'rgb(245, 158, 11)', 'background': 'rgba(245, 158, 11, 0.1)'},  # Yellow
        {'border': 'rgb(239, 68, 68)', 'background': 'rgba(239, 68, 68, 0.1)'},    # Red
        {'border': 'rgb(139, 92, 246)', 'background': 'rgba(139, 92, 246, 0.1)'},  # Purple
    ]
    
    # Get all unique questions answered by any player
    all_questions = CellHistory.objects.filter(
        room=room,
        question_text__isnull=False
    ).values('question_text').distinct()
    
    datasets = []
    for idx, player in enumerate(players):
        color = color_palette[idx % len(color_palette)]
        player_times = []
        for q in all_questions:
            # Get the first attempt for this question by this player
            attempt = CellHistory.objects.filter(
                room=room,
                player=player,
                question_text=q['question_text']
            ).order_by('visited_at').first()
            
            player_times.append(attempt.time_to_answer if attempt else None)
        
        datasets.append({
            'label': f"{player.username}{'(You)' if player == current_user else ''}",
            'data': player_times,
            'borderColor': color['border'],
            'backgroundColor': color['background'],
            'fill': False,
            'tension': 0.4,
            'borderWidth': 2,
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'pointBackgroundColor': color['border'],
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': color['border']
        })
    
    # Get question numbers for labels
    question_numbers = list(range(1, len(all_questions) + 1))
    
    return {
        'labels': [f"Q{i}" for i in question_numbers],
        'datasets': datasets
    }

@login_required
def player_game_report(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    history = CellHistory.objects.filter(room=room, player=request.user)
    
    # Get points data correctly
    player_points = room.points.get(str(request.user.id), 0)
    overall_points_obj = PlayerOverallPoints.objects.get_or_create(player=request.user)[0]
    
    # Get all visited cells (both normal and snake/ladder)
    visited_cells = history.select_related('cell').order_by('visited_at')
    
    # Get unique cells visited by the player
    unique_visited_cells = []
    seen_cells = set()
    
    for visit in visited_cells:
        if visit.cell and visit.cell.number not in seen_cells:
            unique_visited_cells.append({
                'number': visit.cell.number,
                'content': visit.cell.current_content.content if visit.cell.current_content else None,
                'type': visit.cell.cell_type
            })
            seen_cells.add(visit.cell.number)

    # Calculate statistics
    attempted_questions = history.exclude(question_text__isnull=True)
    total_attempted = attempted_questions.count()
    correct_answers = attempted_questions.filter(answer_correct=True).count()
    
    def extract_source_cell(options_str):
        try:
            options = json.loads(options_str) if options_str else []
            if options and isinstance(options, list) and len(options) > 0:
                first_option = options[0]
                if 'Cell ' in first_option:
                    return first_option.split('Cell ')[1].split(':')[0]
        except (json.JSONDecodeError, IndexError, AttributeError):
            pass
        return None
     # Get points data
    player_points = room.points.get(str(request.user.id), 0)
    overall_points = PlayerOverallPoints.objects.get_or_create(player=request.user)[0].total_points
    context = {
        'statistics': {
            'total_questions': total_attempted,
            'correct_answers': correct_answers,
            'avg_time': attempted_questions.aggregate(Avg('time_to_answer'))['time_to_answer__avg'] or 0,
            'total_score': player_points,
            'overall_score': overall_points_obj.total_points,  # Use the object's total_points
            'accuracy': (correct_answers / total_attempted * 100) if total_attempted > 0 else 0,
            'cells_visited': len(unique_visited_cells)
        },
        'visited_cells': unique_visited_cells,
        'time_data': json.dumps(prepare_time_graph_data(attempted_questions)),
        'comparative_time_data': json.dumps(prepare_comparative_time_graph(room, request.user)),
        'question_history': [{
            'question_text': q['question_text'],
            'selected_answer': q['selected_answer'],
            'correct_answer': q['correct_answer'],
            'time_to_answer': q['time_to_answer'],
            'topic_category': q['topic_category'],
            'answer_correct': q['answer_correct'],
            'visited_at': q['visited_at'],
            'options': json.loads(q['options']) if q['options'] else [],
            'current_cell': q['cell__number'],
            'source_cell': q['source_cell']
        } for q in attempted_questions.values(
            'question_text',
            'selected_answer',
            'correct_answer',
            'time_to_answer',
            'topic_category',
            'answer_correct',
            'visited_at',
            'options',
            'cell__number',
            'source_cell'
        ).order_by('-visited_at')],
        'ai_analysis': generate_ai_analysis({
            'total_questions': total_attempted,
            'correct_answers': correct_answers,
            'avg_time': attempted_questions.aggregate(Avg('time_to_answer'))['time_to_answer__avg'] or 0,
            'total_cells_visited': visited_cells.count(),
            'normal_cells_visited': visited_cells.filter(cell__cell_type='NORMAL').count(),
            'total_points': player_points,
            'overall_points': overall_points_obj.total_points  # Use the object's total_points
        })
    }
    
    return render(request, 'game_report.html', context)

def calculate_score(correct, time_taken):
    """Calculate score based on correctness and time taken"""
    base_score = 100 if correct else 0
    time_bonus = max(0, 50 - time_taken) if correct else 0
    return base_score + time_bonus

def get_sample_questions(topic):
    """Get sample questions for topics that need improvement"""
    # Implement question generation or retrieval logic
    return [
        f"Sample question 1 for {topic}",
        f"Sample question 2 for {topic}",
        f"Sample question 3 for {topic}"
    ]

def prepare_time_graph_data(history):
    """Prepare time series data for the response time graph"""
    return {
        'labels': [entry.visited_at.strftime('%H:%M:%S') for entry in history],
        'datasets': [{
            'label': 'Response Time',
            'data': [entry.time_to_answer for entry in history],
            'borderColor': 'rgb(75, 192, 192)',
            'tension': 0.1
        }]
    }

def prepare_topic_graph_data(topic_stats):
    """Prepares data for the radar chart showing topic performance"""
    if not topic_stats:
        return {
            'labels': ['No Data'],
            'datasets': [{
                'label': 'Performance',
                'data': [0],
                'fill': True,
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgb(75, 192, 192)',
            }]
        }
    
    return {
        'labels': [topic.get('name', 'Uncategorized') for topic in topic_stats],
        'datasets': [
            {
                'label': 'Topic Accuracy',
                'data': [topic.get('accuracy', 0) for topic in topic_stats],
                'fill': True,
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgb(75, 192, 192)',
            },
            {
                'label': 'Response Speed',
                'data': [max(0, 100 - (topic.get('avg_time', 0) * 5)) for topic in topic_stats],
                'fill': True,
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'borderColor': 'rgb(255, 99, 132)',
            }
        ]
    }

def generate_ai_analysis(player_data):
    """Generate AI analysis of player performance using Gemini"""
    try:
        genai.configure(api_key='AIzaSyA8GHU0QhwXkgCXEBYnost56YOPmsd2pPs')
        model = genai.GenerativeModel('gemini-pro')
        
        # Format the topics list for the prompt
        topics_list = "\n".join([f"- {topic}" for topic in player_data.get('topics_covered', [])])
        
        prompt = f"""
        Analyze this player's game performance:

        Statistics:
        - Total Questions Attempted: {player_data['total_questions']}
        - Correct Answers: {player_data['correct_answers']}
        - Average Response Time: {player_data['avg_time']:.1f} seconds
        - Accuracy: {(player_data['correct_answers'] / player_data['total_questions'] * 100) if player_data['total_questions'] > 0 else 0:.1f}%

        Topics Covered:
        {topics_list}

        Please provide analysis in this format:

        1. Brief Summary of Overall Performance
        2. Time Management Analysis
        3. Specific Recommendations for Improvement

        Keep the analysis concise and focused on these aspects.
        """
        
        response = model.generate_content(prompt)
        analysis_text = response.text
        
        # Split the analysis into sections
        sections = analysis_text.split('\n\n')
        
        return {
            'summary': sections[0] if sections else "Analysis not available",
            'detailed_analysis': {
                'overall_performance': sections[0] if len(sections) > 0 else "",
                'time_analysis': sections[1] if len(sections) > 1 else "",
                'recommendations': sections[2] if len(sections) > 2 else ""
            },
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"AI Analysis Error: {str(e)}")
        return {
            'error': str(e),
            'summary': "Unable to generate AI analysis",
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def get_topic_analysis(history):
    """
    Analyzes performance by topic from cell history
    Returns list of topic stats with accuracy and timing metrics
    """
    topic_stats = []
    
    # Get unique topics
    topics = history.values('topic_category').distinct()
    
    for topic in topics:
        topic_category = topic['topic_category']
        if not topic_category:  # Skip if topic is None
            continue
            
        # Get questions for this topic
        topic_questions = history.filter(topic_category=topic_category)
        total = topic_questions.count()
        
        if total > 0:  # Only include topics with questions
            correct = topic_questions.filter(answer_correct=True).count()
            avg_time = topic_questions.aggregate(Avg('time_to_answer'))['time_to_answer__avg'] or 0
            
            topic_stats.append({
                'name': topic_category,
                'total': total,
                'correct': correct,
                'accuracy': (correct / total * 100),
                'avg_time': avg_time,
                'questions': list(topic_questions.values(
                    'question_text',
                    'selected_answer',
                    'correct_answer',
                    'answer_correct',
                    'time_to_answer'
                ))
            })
    
    # Sort by accuracy (highest first)
    topic_stats.sort(key=lambda x: x['accuracy'], reverse=True)
    
    return topic_stats

def format_topic_analysis(topics):
    """Formats topic analysis for AI prompt"""
    if not topics:
        return "No topic data available"
        
    result = []
    for topic in topics:
        result.append(
            f"Topic: {topic['name']}\n"
            f"- Accuracy: {topic['accuracy']:.1f}%\n"
            f"- Questions Attempted: {topic['total']}\n"
            f"- Average Response Time: {topic['avg_time']:.1f}s"
        )
    return "\n\n".join(result)

def format_question_history(questions):
    """Formats question history for AI prompt"""
    if not questions:
        return "No question history available"
        
    result = []
    for q in questions:
        result.append(
            f"Question: {q['question_text']}\n"
            f"Selected: {q['selected_answer']}\n"
            f"Correct: {q['correct_answer']}\n"
            f"Time: {q['time_to_answer']}s\n"
            f"Topic: {q['topic_category']}\n"
            f"Result: {'Correct' if q['answer_correct'] else 'Incorrect'}"
        )
    return "\n\n".join(result)

@login_required
def room_state(request, room_id):
    """API endpoint to get current room state"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.refresh_from_db()
        
        players_data = [{
            'username': player.username,
            'is_creator': player == room.creator
        } for player in room.players.all()]
        
        return JsonResponse({
            'players': players_data,
            'game_started': not room.is_active,
            'timestamp': time.time()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def initialize_cells():
    """
    Creates all 100 cells for the game board if they don't exist
    Sets up snake and ladder positions
    This should be called before starting any game
    """
    # Check if cells already exist
    if Cell.objects.exists():
        print("Cells already initialized")
        return
        
    print("Initializing cells for the first time...")
    
    # Define snake and ladder cells
    snake_ladder_cells = [
        # Some key snake/ladder positions
        4, 9, 17, 20, 28, 40, 51, 54, 62, 63, 71, 80, 87, 93, 95, 99
    ]
    
    # Create all cells in a single transaction for efficiency
    with transaction.atomic():
        for i in range(1, 101):
            cell_type = 'SNAKE_LADDER' if i in snake_ladder_cells else 'NORMAL'
            Cell.objects.create(
                number=i,
                cell_type=cell_type
            )
    
    print(f"Created 100 cells with {len(snake_ladder_cells)} snake/ladder cells")

@login_required
def start_game(request, room_id):
    """Start a game with the selected content"""
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Check if user is the creator of the room
    if request.user != room.creator:
        messages.error(request, "Only the room creator can start the game.")
        return redirect('snake_ladder:room_detail', room_id=room_id)
    
    # Check if game is already active
    if not room.is_active:
        return redirect('snake_ladder:game_board', room_id=room_id)
    
    # Initialize cells if they don't exist
    initialize_cells()
    
    # Prepare cells with content
    reset_all_cells = Cell.objects.all()
    for cell in reset_all_cells:
        cell.contents.clear()
        cell.current_content = None
        cell.save()
    
    # Get content for this game based on session
    using_dynamic_content = request.session.get('using_dynamic_content', False)
    content_source = None
    
    if using_dynamic_content:
        # Get session data
        topic_group_id = request.session.get('topic_group_id')
        summary_id = request.session.get('summary_id')
        
        if topic_group_id and summary_id:
            try:
                from dynamicDB.models import MainTopic, SubTopic
                # Get the topic and summary
                topic_group = MainTopic.objects.get(pk=topic_group_id)
                summary_topic = SubTopic.objects.get(pk=summary_id, topic_group=topic_group)
                
                # Get all main topics and their chapters
                all_content = []
                
                for main_topic in summary_topic.main_topics.all():
                    for chapter in main_topic.chapters.all():
                        all_content.append({
                            'title': f"{main_topic.title}: {chapter.title}",
                            'content': chapter.content
                        })
                
                # If we have content, use it for the game
                if all_content:
                    content_source = all_content
                    print(f"Using dynamic content with {len(all_content)} items")
            except Exception as e:
                print(f"Error loading dynamic content: {e}")
    
    # If no dynamic content, use traditional part/type
    if not content_source:
        # Get part and type from session or room
        part = request.session.get('checkpoint_part', room.current_content_part or 5)
        type_code = request.session.get('checkpoint_type', room.current_content_type or 'JUD')
        
        # Ensure room content type is set
        if not room.current_content_part:
            room.current_content_part = part
            room.current_content_type = type_code
            room.save()
        
        print(f"Using traditional content from Part {part} {type_code}")
    
    # Prepare the board with content
    cells = Cell.objects.all().order_by('number')
    
    # Use the appropriate content source
    if content_source:
        # Use the dynamic content for all cells (including snake and ladder cells)
        for cell in cells:
            # Pick a random content item
            if content_source:
                content_item = random.choice(content_source)
                
                # Create a CellContent object
                cell_content = CellContent.objects.create(
                    content=content_item['content'],
                    topic=content_item['title']
                )
                
                # Add to cell
                cell.contents.add(cell_content)
                cell.current_content = cell_content
                cell.save()
    else:
        # Use the traditional game content method, but ensure snake/ladder cells also get content
        # First, set up normal cells using the existing method
        room.set_game_content_type(part=room.current_content_part, type=room.current_content_type)
        
        # Now handle snake/ladder cells that might not have content
        snake_ladder_cells = Cell.objects.filter(cell_type='SNAKE_LADDER')
        
        # Get available facts to use for snake/ladder cells
        facts = []
        try:
            # Try to get GameFacts
            from snake_ladder.models import GameFact
            facts = list(GameFact.objects.all())
        except:
            # Fallback to existing cell content
            normal_cell_content = CellContent.objects.filter(cells__cell_type='NORMAL').distinct()
            if normal_cell_content.exists():
                facts = list(normal_cell_content)
        
        # If we have facts, assign to snake/ladder cells
        if facts:
            for cell in snake_ladder_cells:
                if not cell.current_content:  # Only update if content is missing
                    # Get a random fact
                    fact = random.choice(facts)
                    
                    # Create a CellContent or use existing
                    if hasattr(fact, 'content'):
                        # It's a CellContent object
                        cell_content = fact
                    else:
                        # It's a GameFact object
                        cell_content = CellContent.objects.create(
                            content=fact.fact_text,
                            topic="Snake & Ladder Special",
                            part=room.current_content_part,
                            type=room.current_content_type
                        )
                    
                    # Add to cell
                    cell.contents.add(cell_content)
                    cell.current_content = cell_content
                    cell.save()
    
    # Create initial positions for all players
    for player in room.players.all():
        PlayerPosition.objects.get_or_create(
            room=room,
            player=player,
            defaults={'position': 1}
        )
    
    # Mark game as started
    room.is_active = False  # This means game has started (active=false means game in progress)
    room.save()
        
    # Redirect to game board
    messages.success(request, "Game started! Roll the dice to begin.")
    return redirect('snake_ladder:game_board', room_id=room_id)

@login_required
def snake_ladder_intro(request):
    """
    View to show the Snake & Ladder intro/create room page
    """
    return render(request, 'create_room.html')

@login_required
def cell_content_details(request, part=None, type=None):
    """
    Display all cell contents with highlighting for topics where user struggled
    """
    show_highlighted = request.GET.get('show_highlighted') == 'true'
    selected_part = request.GET.get('part')
    selected_type = request.GET.get('type')
    
    print("\n=== HIGHLIGHTED CONTENT SUMMARY ===")
    
    # Get incorrect history with more detailed query
    incorrect_history = CellHistory.objects.filter(
        player=request.user,
        answer_correct=False
    ).select_related('cell', 'cell__current_content')
    
    print("\nFetching incorrect answers:")
    for history in incorrect_history:
        print(f"Question: {history.question_text}")
        print(f"Topic Category: {history.topic_category}")
        if history.cell and history.cell.current_content:
            print(f"Content Topic: {history.cell.current_content.topic}")
        print("---")
    
    # Collect incorrect topics (case-insensitive)
    incorrect_topics = set()
    for history in incorrect_history:
        if history.topic_category:
            incorrect_topics.add(history.topic_category.lower())
        if history.cell and history.cell.current_content and history.cell.current_content.topic:
            incorrect_topics.add(history.cell.current_content.topic.lower())
    
    print("\nTopics from incorrect answers:")
    for topic in incorrect_topics:
        print(f"- {topic}")
    
    # Get all cell contents
    cell_contents = CellContent.objects.all().order_by('part', 'type')
    
    # Apply filters
    if selected_part:
        cell_contents = cell_contents.filter(part=selected_part)
    if selected_type:
        cell_contents = cell_contents.filter(type=selected_type)
    
    print("\nContent items that need review:")
    print("--------------------------------")
    
    highlighted_items = []
    for item in cell_contents:
        # Convert item topic to lowercase for comparison
        item_topic = item.topic.lower() if item.topic else ''
        item_content = item.content.lower() if item.content else ''
        
        # Check for topic matches
        topic_matches = []
        for topic in incorrect_topics:
            if (topic in item_topic) or (topic in item_content):
                topic_matches.append(topic)
        
        needs_review = bool(topic_matches)
        
        if needs_review:
            print(f"\nContent Item {len(highlighted_items) + 1}:")
            print(f"Part: {item.part}")
            print(f"Type: {item.get_type_display() if item.type else 'No Type'}")
            print(f"Topic: {item.topic}")
            print(f"Content Preview: {item.content[:100]}...")
            print(f"Matching topics: {topic_matches}")
            print("--------------------------------")
            
            highlighted_items.append(item)
    
    print(f"\nTotal highlighted items: {len(highlighted_items)}")
    print("=====================================\n")
    
    def slice_content_items(items, per_page=2):
        content_list = []
        for item in items:
            item_topic = item.topic.lower() if item.topic else ''
            item_content = item.content.lower() if item.content else ''
            
            # Check for topic matches
            topic_matches = []
            for topic in incorrect_topics:
                if (topic in item_topic) or (topic in item_content):
                    topic_matches.append(topic)
            
            needs_review = bool(topic_matches)
            
            if show_highlighted and not needs_review:
                continue
                
            content_dict = {
                'content': item,
                'needs_review': needs_review,
                'related_topics': topic_matches
            }
            content_list.append(content_dict)
        
        if content_list:
            return [content_list[i:i + per_page] for i in range(0, len(content_list), per_page)]
        return []

    content_items = slice_content_items(list(cell_contents))
    
    try:
        bookmark = CellBookmark.objects.get(user=request.user)
        bookmark_info = {
            'page_number': bookmark.page_number,
            'has_bookmark': True
        }
        print(f"Found bookmark at page {bookmark.page_number}")
    except CellBookmark.DoesNotExist:
        bookmark_info = {
            'has_bookmark': False
        }

    total_items = len(content_items) * 2 if content_items else 0
    current_page = int(request.GET.get('page', 1))
    
    context = {
        'content_items': content_items,
        'bookmark': bookmark_info,
        'selected_part': selected_part,
        'selected_type': selected_type,
        'PART_CHOICES': {5: 'Part 5', 6: 'Part 6'},
        'TYPE_CHOICES': {
            'JUD': 'Judiciary',
            'LEG': 'Legislative',
            'EXEC': 'Executive'
        },
        'incorrect_topics': list(incorrect_topics),
        'show_highlighted': show_highlighted,
        'page_obj': {
            'number': current_page,
            'has_previous': current_page > 1,
            'has_next': current_page < len(content_items),
            'previous_page_number': current_page - 1,
            'next_page_number': current_page + 1,
            'start_index': (current_page - 1) * 2 + 1 if total_items > 0 else 0,
            'end_index': min(current_page * 2, total_items),
            'paginator': {'count': total_items, 'num_pages': len(content_items)}
        }
    }
    
    return render(request, 'snake_ladder/cell_content_details.html', context)

@login_required
@require_http_methods(["POST"])
def update_bookmark(request):
    """Update the user's bookmark position"""
    try:
        data = json.loads(request.body)
        bookmark, created = CellBookmark.objects.update_or_create(
            user=request.user,
            defaults={'page_number': data['page_number']}
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_bookmark(request):
    """Get the user's current bookmark"""
    try:
        bookmark = CellBookmark.objects.get(user=request.user)
        return JsonResponse({
            'success': True,
            'page_number': bookmark.page_number
        })
    except CellBookmark.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No bookmark found'})

@login_required
def generate_cell_content(request, room_id):
    """
    Generates cell content for the game based on room context
    1. Uses AI to generate relevant content if needed
    2. Creates cell content entries for the game
    3. Redirects back to room page with success message
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Check if user is the creator of the room
    if request.user != room.creator:
        messages.error(request, "Only the room creator can generate content.")
        return redirect('snake_ladder:room_detail', room_id=room_id)
    
    try:
        # Initialize cells if they don't exist
        initialize_cells()
        
        # Determine content source (from session or room)
        using_dynamic_content = request.session.get('using_dynamic_content', False)
        
        if using_dynamic_content:
            # Get session data
            topic_group_id = request.session.get('topic_group_id')
            summary_id = request.session.get('summary_id')
            
            if topic_group_id and summary_id:
                try:
                    from dynamicDB.models import MainTopic, SubTopic
                    # Get the topic and summary
                    topic_group = MainTopic.objects.get(pk=topic_group_id)
                    summary_topic = SubTopic.objects.get(pk=summary_id, topic_group=topic_group)
                    
                    # Get main topics and chapters
                    for main_topic in summary_topic.main_topics.all():
                        for chapter in main_topic.chapters.all():
                            # Create cell content
                            CellContent.objects.create(
                                content=chapter.content,
                                topic=f"{main_topic.title}: {chapter.title}",
                                part=room.current_content_part or 5,
                                type=room.current_content_type or 'JUD'
                            )
                    
                    messages.success(request, f"Content generated successfully from '{summary_topic.title}'!")
                except Exception as e:
                    print(f"Error generating dynamic content: {e}")
                    messages.warning(request, "Could not generate content from dynamic source.")
            else:
                messages.warning(request, "Missing topic information for content generation.")
        else:
            # Traditional content creation from part/type
            part = room.current_content_part or request.session.get('checkpoint_part', 5)
            type_code = room.current_content_type or request.session.get('checkpoint_type', 'JUD')
            
            # Check if we already have content for this part/type
            existing_content = CellContent.objects.filter(part=part, type=type_code)
            
            if existing_content.exists():
                messages.info(request, f"Using existing content for Part {part} {type_code}.")
            else:
                # Generate facts from CSV or use AI to create some basic content
                try:
                    # Try to import CSV data
                    import csv
                    import os
                    from django.conf import settings
                    
                    csv_path = os.path.join(settings.BASE_DIR, 'snake_ladder', 'iks1.csv')
                    if os.path.exists(csv_path):
                        with open(csv_path, newline='', encoding='utf-8') as csvfile:
                            reader = csv.reader(csvfile)
                            next(reader)  # Skip header
                            count = 0
                            for row in reader:
                                if len(row) >= 2 and count < 100:  # Limit to 100 facts
                                    topic = row[0] if row[0] else "Constitutional Fact"
                                    content = row[1] if len(row) > 1 else "Important constitutional fact"
                                    
                                    CellContent.objects.create(
                                        content=content,
                                        topic=topic,
                                        part=part,
                                        type=type_code
                                    )
                                    count += 1
                        
                        messages.success(request, f"Generated {count} content items from CSV data!")
                    else:
                        # Use AI to create basic content if CSV not found
                        genai.configure(api_key='AIzaSyA8DaPlDtUTyzwjo8M6aOwFcfGDLU7itJg')
                        model = genai.GenerativeModel('gemini-1.5-pro')
                        
                        # Create prompts for different content types
                        type_names = {
                            'JUD': 'Judiciary',
                            'LEG': 'Legislative',
                            'EXEC': 'Executive'
                        }
                        
                        prompt = f"""Generate 20 educational facts about the Indian Constitution related to Part {part} {type_names.get(type_code, type_code)}.
                        Each fact should be 2-3 sentences long and informative for educational purposes.
                        For each fact, also provide a short 2-3 word topic title.
                        
                        Format: JSON array with objects containing 'topic' and 'content' keys.
                        Example: [
                            {{"topic": "Fundamental Rights", "content": "Article 14 guarantees equality before law. It ensures that no person shall be denied equality before the law or equal protection of the laws."}},
                            {{"topic": "Directive Principles", "content": "Article 39 directs the state to ensure that citizens have the right to adequate means of livelihood. It also aims to prevent concentration of wealth and means of production."}}
                        ]
                        """
                        
                        response = model.generate_content(prompt)
                        try:
                            # Parse the response as JSON
                            import json
                            response_text = response.text.strip()
                            
                            # Handle markdown code blocks
                            if response_text.startswith("```json") and response_text.endswith("```"):
                                response_text = response_text[7:-3].strip()
                            
                            facts = json.loads(response_text)
                            for fact in facts:
                                CellContent.objects.create(
                                    content=fact.get('content', 'Constitutional fact'),
                                    topic=fact.get('topic', 'Constitution'),
                                    part=part,
                                    type=type_code
                                )
                            
                            messages.success(request, f"Generated {len(facts)} content items using AI!")
                        except json.JSONDecodeError:
                            # Fallback to creating a few basic entries
                            topics = ["Fundamental Rights", "Directive Principles", "Parliament", "Executive", "Judiciary"]
                            for i in range(10):
                                CellContent.objects.create(
                                    content=f"Important fact about {type_names.get(type_code, type_code)} in the Constitution of India (#{i+1}).",
                                    topic=random.choice(topics),
                                    part=part,
                                    type=type_code
                                )
                            messages.success(request, "Generated 10 basic content items!")
                except Exception as e:
                    print(f"Error generating content: {e}")
                    messages.warning(request, f"Error generating content: {str(e)}")
        
        # Return to room detail page
        return redirect('snake_ladder:room_detail', room_id=room_id)
    except Exception as e:
        messages.error(request, f"Error generating content: {str(e)}")
        return redirect('snake_ladder:room_detail', room_id=room_id)
