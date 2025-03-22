from django.shortcuts import render
from dbs.models import ConstitutionalArticle
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from .models import PlayerPlatPoints
from django.utils import timezone
from spinwheel.models import PlayerProfile, PlayerCollection
from django.db.models import Count
import json 
from django.views.decorators.http import require_http_methods
from .models import ArticleBookmark
from gtts import gTTS
import io


@login_required
def profile(request):
    print("\n=== Debugging from Plat: profile view ===")
    print(f"Loading profile for user: {request.user.username}")
    
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    print(f"Player points {'created' if created else 'retrieved'}")
    
    # First sync all game data to ensure latest points
    print("Starting data sync...")
    sync_success = player_points.sync_all_game_data()
    print(f"Data sync {'successful' if sync_success else 'failed'}")
    
    # Refresh player_points from database after sync
    player_points.refresh_from_db()
    
    # Now update game statistics with synced data
    game_stats = player_points.update_game_stats()
    print("Game stats updated")
    print(f"Current stats: {game_stats}")
    
    # Use the synced points
    snake_ladder_points = player_points.snake_ladder_points
    housie_points = player_points.housie_points
    spinwheel_coins = player_points.spinwheel_coins
    flipcard_points = player_points.flipcard_points
    
    # Calculate total points with synced data
    total_points = (
        snake_ladder_points +
        housie_points +
        flipcard_points
    )
    
    print(f"[DEBUG] Profile points - Snake Ladder: {snake_ladder_points}, Total: {total_points}")
    
    # Update if total has changed
    if total_points != player_points.total_points:
        player_points.total_points = total_points
        player_points.save()
    
    # Get checkpoint progress
    progress = player_points.get_checkpoint_progress()
    
    # Debug print statements
    print(f"Total Points: {player_points.total_points}")
    print(f"Current Part: {player_points.current_part}")
    print(f"Current Type: {player_points.current_type}")
    print("Completed Checkpoints:", player_points.completed_checkpoints)
    print("Progress:", progress)
    
    # Force unlock check for all checkpoints based on points
    for part in [5, 6]:
        for type_ in ['JUD', 'LEG', 'EXEC']:
            if player_points.can_unlock_checkpoint(part, type_):
                checkpoint_key = f"{part}_{type_}"
                if checkpoint_key not in player_points.completed_checkpoints:
                    player_points.completed_checkpoints[checkpoint_key] = {
                        'completed_at': timezone.now().isoformat(),
                        'points': player_points.total_points
                    }
    player_points.save()
    
    # Get articles for each checkpoint with progress info
    checkpoints = {
        5: {
            'JUD': {
                'articles': ConstitutionalArticle.objects.filter(part=5, type='JUD'),
                'progress': progress[5]['JUD'],
                'count': ConstitutionalArticle.objects.filter(part=5, type='JUD').count(),
                'is_current': player_points.current_part == 5 and player_points.current_type == 'JUD',
                'is_part_five': True
            },
            'LEG': {
                'articles': ConstitutionalArticle.objects.filter(part=5, type='LEG'),
                'progress': progress[5]['LEG'],
                'count': ConstitutionalArticle.objects.filter(part=5, type='LEG').count(),
                'is_current': player_points.current_part == 5 and player_points.current_type == 'LEG',
                'is_part_five': True
            },
            'EXEC': {
                'articles': ConstitutionalArticle.objects.filter(part=5, type='EXEC'),
                'progress': progress[5]['EXEC'],
                'count': ConstitutionalArticle.objects.filter(part=5, type='EXEC').count(),
                'is_current': player_points.current_part == 5 and player_points.current_type == 'EXEC',
                'is_part_five': True
            },
        },
        6: {
            'EXEC': {
                'articles': ConstitutionalArticle.objects.filter(part=6, type='EXEC'),
                'progress': progress[6]['EXEC'],
                'count': ConstitutionalArticle.objects.filter(part=6, type='EXEC').count(),
                'is_current': player_points.current_part == 6 and player_points.current_type == 'EXEC',
                'is_part_five': False
            },
            'LEG': {
                'articles': ConstitutionalArticle.objects.filter(part=6, type='LEG'),
                'progress': progress[6]['LEG'],
                'count': ConstitutionalArticle.objects.filter(part=6, type='LEG').count(),
                'is_current': player_points.current_part == 6 and player_points.current_type == 'LEG',
                'is_part_five': False
            },
            'JUD': {
                'articles': ConstitutionalArticle.objects.filter(part=6, type='JUD'),
                'progress': progress[6]['JUD'],
                'count': ConstitutionalArticle.objects.filter(part=6, type='JUD').count(),
                'is_current': player_points.current_part == 6 and player_points.current_type == 'JUD',
                'is_part_five': False
            },
        }
    }
    
    
    context = {
        'checkpoints': checkpoints,
        'player_points': player_points,
        'game_points': {
            'snake_ladder': snake_ladder_points,
            'housie': housie_points,
            'spinwheel': spinwheel_coins,
            'flipcard': flipcard_points
        },
        'total_points': total_points,
        'game_stats': game_stats,
    }
    return render(request, 'plat/profile.html', context)

@login_required
def checkpoint_detail(request, part, type):
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    
    # Verify checkpoint is unlocked
    if not player_points.can_unlock_checkpoint(part, type):
        return HttpResponseForbidden("This checkpoint is locked!")
    
    # Get articles for this checkpoint
    articles = ConstitutionalArticle.objects.filter(
        part=part,
        type=type
    ).order_by('article_number')
    
    # Prepare articles data
    articles_data = []
    type_names = {
        'JUD': 'Judiciary',
        'LEG': 'Legislative',
        'EXEC': 'Executive'
    }
    
    for article in articles:
        articles_data.append({
            'number': article.article_number,
            'title': article.article_title,
            'explanation': article.simplified_explanation
        })
    
    print(f"[DEBUG] Checkpoint detail requested - Part: {part}, Type: {type}")
    print(f"[DEBUG] Found {len(articles_data)} articles")
    
    # Return JSON response with checkpoint info
    return JsonResponse({
        'part': part,
        'type': type,
        'type_display': type_names.get(type, type),
        'articles': articles_data,
        'checkpoint_part': part,
        'checkpoint_type': type
    })

@login_required
def leaderboard(request):
    # Get all players with their points
    all_players = PlayerPlatPoints.objects.all()
    
    # Overall Leaderboard (sorted by total points, excluding spinwheel)
    overall_leaders = all_players.order_by('-total_points')[:10]
    
    # Game-specific Leaderboards
    snake_ladder_leaders = all_players.order_by('-snake_ladder_points')[:10]
    housie_leaders = all_players.order_by('-housie_points')[:10]
    
    # Spinwheel leaders - Fetch directly from PlayerProfile for coins
    spinwheel_profiles = PlayerProfile.objects.all().order_by('-coins')[:10]
    
    # Create a list to store combined spinwheel data
    spinwheel_leaders = []
    
    for profile in spinwheel_profiles:
        # Get card counts for this player
        card_counts = PlayerCollection.objects.filter(
            player=profile,
            quantity__gt=0
        ).values('card__rarity').annotate(
            count=Count('card')
        )
        
        # Initialize card counts
        common = rare = epic = 0
        
        # Count cards by rarity
        for count_data in card_counts:
            if count_data['card__rarity'] == 'COMMON':
                common = count_data['count']
            elif count_data['card__rarity'] == 'RARE':
                rare = count_data['count']
            elif count_data['card__rarity'] == 'EPIC':
                epic = count_data['count']
        
        # Create a data object for the template
        leader_data = {
            'player': profile.user,
            'spinwheel_coins': profile.coins,
            'common_cards': common,
            'rare_cards': rare,
            'epic_cards': epic,
            'total_cards': common + rare + epic
        }
        spinwheel_leaders.append(leader_data)
    
    flipcard_leaders = all_players.order_by('-flipcard_points')[:10]
    
    context = {
        'overall_leaders': overall_leaders,
        'snake_ladder_leaders': snake_ladder_leaders,
        'housie_leaders': housie_leaders,
        'spinwheel_leaders': spinwheel_leaders,
        'flipcard_leaders': flipcard_leaders,
    }
    
    return render(request, 'plat/leaderboard.html', context)

@login_required
def article_details(request, part, type):
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    
    # Verify checkpoint is unlocked
    if not player_points.can_unlock_checkpoint(part, type):
        return HttpResponseForbidden("This checkpoint is locked!")
    
    # Get articles for this checkpoint
    articles = ConstitutionalArticle.objects.filter(
        part=part,
        type=type
    ).order_by('article_number')
    
    type_names = {
        'JUD': 'Judiciary',
        'LEG': 'Legislative',
        'EXEC': 'Executive'
    }
    
    context = {
        'part': part,
        'type': type_names.get(type, type),
        'articles': articles,
    }
    
    # Get bookmark info
    try:
        bookmark = ArticleBookmark.objects.get(user=request.user)
        context['bookmark'] = {
            'page_number': bookmark.page_number,
            'has_bookmark': True
        }
    except ArticleBookmark.DoesNotExist:
        context['bookmark'] = {
            'has_bookmark': False
        }
    
    return render(request, 'plat/article_details.html', context)

@login_required
@require_http_methods(["POST"])
def add_bookmark(request):
    try:
        data = json.loads(request.body)
        bookmark, created = ArticleBookmark.objects.update_or_create(
            user=request.user,
            defaults={
                'part': data['part'],
                'type': data['type'],
                'page_number': data['page_number']
            }
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_bookmark(request):
    try:
        bookmark = ArticleBookmark.objects.get(user=request.user)
        return JsonResponse({
            'success': True,
            'part': bookmark.part,
            'type': bookmark.type,
            'page_number': bookmark.page_number
        })
    except ArticleBookmark.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No bookmark found'})

@login_required
def get_speech(request):
    try:
        text = request.GET.get('text', '')
        if not text:
            return JsonResponse({'error': 'No text provided'}, status=400)

        # Create gTTS object
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Create a bytes buffer
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        # Return audio file
        response = HttpResponse(fp.read(), content_type='audio/mpeg')
        response['Content-Disposition'] = 'attachment; filename="speech.mp3"'
        return response
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

