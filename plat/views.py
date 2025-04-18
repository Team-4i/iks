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
from dynamicDB.models import ActiveTopicGroups, MainTopic, SummaryTopic


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
    
    # Get active topic groups from dynamicDB
    active_topic_groups = ActiveTopicGroups.get_active_groups().order_by('topic_group__id')
    
    # Build a dictionary similar to checkpoints but using topic groups
    topic_group_data = {}
    
    # Create "Parts" from active topic groups (if there are active groups)
    if active_topic_groups.exists():
        for i, active_group in enumerate(active_topic_groups):
            topic_group = active_group.topic_group
            part_num = i + 5  # Use 5 and 6 as part numbers (for compatibility)
            
            topic_group_data[part_num] = {}
            
            # Get summary topics for this group instead of the top 3 main topics
            summary_topics = SummaryTopic.objects.filter(topic_group=topic_group).order_by('order')[:3]
            
            # If no summary topics exist, generate them on-the-fly
            if not summary_topics.exists():
                # Fall back to using top 3 main topics directly
                main_topics = topic_group.topics.all().order_by('id')[:3]
                
                # Create entries for each topic (analogous to JUD/LEG/EXEC)
                for j, topic in enumerate(main_topics):
                    # Map to JUD/LEG/EXEC for compatibility
                    type_code = ['JUD', 'LEG', 'EXEC'][min(j, 2)]
                    
                    # Get checkpoint progress if available, otherwise create default
                    checkpoint_progress = {}
                    if part_num in progress and type_code in progress[part_num]:
                        checkpoint_progress = progress[part_num][type_code]
                    else:
                        checkpoint_progress = {
                            'required_points': part_num * 100 + j * 100,  # Simple formula for points
                            'completed': False,
                            'unlocked': part_num == 5 and j == 0  # First topic is unlocked
                        }
                    
                    topic_group_data[part_num][type_code] = {
                        'articles': [],  # No articles yet, could fetch from appropriate source
                        'progress': checkpoint_progress,
                        'count': topic.chapters.count(),  # Number of chapters instead of articles
                        'is_current': part_num == player_points.current_part and type_code == player_points.current_type,
                        'is_part_five': part_num == 5,
                        'main_topic_title': topic.title,  # Store the actual topic title
                        'main_topic_id': topic.id
                    }
            else:
                # Use summary topics
                for j, summary_topic in enumerate(summary_topics):
                    # Map to JUD/LEG/EXEC for compatibility
                    type_code = ['JUD', 'LEG', 'EXEC'][min(j, 2)]
                    
                    # Get checkpoint progress if available, otherwise create default
                    checkpoint_progress = {}
                    if part_num in progress and type_code in progress[part_num]:
                        checkpoint_progress = progress[part_num][type_code]
                    else:
                        checkpoint_progress = {
                            'required_points': part_num * 100 + j * 100,  # Simple formula for points
                            'completed': False,
                            'unlocked': part_num == 5 and j == 0  # First topic is unlocked
                        }
                    
                    # Count all chapters from all main topics in this summary topic
                    chapter_count = 0
                    for main_topic in summary_topic.main_topics.all():
                        chapter_count += main_topic.chapters.count()
                    
                    topic_group_data[part_num][type_code] = {
                        'articles': [],  # No articles yet, could fetch from appropriate source
                        'progress': checkpoint_progress,
                        'count': chapter_count,  # Total number of chapters across all main topics
                        'is_current': part_num == player_points.current_part and type_code == player_points.current_type,
                        'is_part_five': part_num == 5,
                        'main_topic_title': summary_topic.title,  # Use summary topic title
                        'main_topic_id': summary_topic.id,  # Store summary topic ID
                        'is_summary_topic': True,  # Mark as summary topic
                        'summary_description': summary_topic.description,  # Add summary description
                        'main_topics_count': summary_topic.main_topics.count()  # Number of main topics in this summary
                    }
    else:
        # Fallback to default checkpoints if no active topic groups
        topic_group_data = {
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
        'checkpoints': topic_group_data,
        'player_points': player_points,
        'game_points': {
            'snake_ladder': snake_ladder_points,
            'housie': housie_points,
            'spinwheel': spinwheel_coins,
            'flipcard': flipcard_points
        },
        'total_points': total_points,
        'game_stats': game_stats,
        'active_topic_groups': active_topic_groups,
        'using_dynamic_topics': active_topic_groups.exists(),
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
    
    # Get active topic groups
    active_topic_groups = ActiveTopicGroups.get_active_groups()
    
    # Check if we're using dynamic topics
    if active_topic_groups.exists():
        # Map the part and type to a topic group and main topic
        try:
            # Get the topic group based on part number (5 or 6)
            topic_group_index = part - 5
            if topic_group_index < 0 or topic_group_index >= active_topic_groups.count():
                return HttpResponseForbidden("Invalid topic group")
            
            active_group = active_topic_groups[topic_group_index]
            topic_group = active_group.topic_group
            
            # Check if a summary topic ID was specified in the request
            summary_topic_id = request.GET.get('summary_id')
            
            if summary_topic_id:
                # User clicked on a summary topic, show all main topics from this summary
                try:
                    summary_topic = SummaryTopic.objects.get(id=summary_topic_id, topic_group=topic_group)
                    
                    # Get all main topics from this summary topic
                    main_topics = summary_topic.main_topics.all().order_by('id')
                    
                    # Prepare all chapters from all these main topics
                    all_chapters_data = []
                    
                    for main_topic in main_topics:
                        chapters = main_topic.chapters.all().order_by('order')
                        
                        # Add a header for each main topic
                        all_chapters_data.append({
                            'number': 0,  # Use 0 to identify as header
                            'title': f"--- {main_topic.title} ---",
                            'explanation': main_topic.summary,
                            'is_header': True
                        })
                        
                        # Add all chapters for this main topic
                        for chapter in chapters:
                            all_chapters_data.append({
                                'number': chapter.order,
                                'title': chapter.title,
                                'explanation': chapter.content,
                                'is_header': False
                            })
                    
                    # Return JSON response with summary topic info
                    return JsonResponse({
                        'part': part,
                        'type': type,
                        'type_display': summary_topic.title,
                        'articles': all_chapters_data,
                        'checkpoint_part': part,
                        'checkpoint_type': type,
                        'is_dynamic': True,
                        'is_summary': True,
                        'topic_group': topic_group.title,
                        'summary_topic': summary_topic.title,
                        'summary_description': summary_topic.description,
                        'main_topics_count': main_topics.count()
                    })
                
                except SummaryTopic.DoesNotExist:
                    # Fallback to standard approach if summary topic not found
                    pass
            
            # Standard approach - get main topic based on type (JUD/LEG/EXEC)
            type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(type, 0)
            
            # First check if there are summary topics for this group
            summary_topics = SummaryTopic.objects.filter(topic_group=topic_group).order_by('order')
            
            if summary_topics.exists() and type_index < summary_topics.count():
                # Use summary topic
                summary_topic = summary_topics[type_index]
                
                # Get all main topics from this summary topic
                main_topics = summary_topic.main_topics.all().order_by('id')
                
                # Prepare all chapters from all these main topics
                all_chapters_data = []
                
                for main_topic in main_topics:
                    chapters = main_topic.chapters.all().order_by('order')
                    
                    # Add a header for each main topic
                    all_chapters_data.append({
                        'number': 0,  # Use 0 to identify as header
                        'title': f"--- {main_topic.title} ---",
                        'explanation': main_topic.summary,
                        'is_header': True
                    })
                    
                    # Add all chapters for this main topic
                    for chapter in chapters:
                        all_chapters_data.append({
                            'number': chapter.order,
                            'title': chapter.title,
                            'explanation': chapter.content,
                            'is_header': False
                        })
                
                # Return JSON response with summary topic info
                return JsonResponse({
                    'part': part,
                    'type': type,
                    'type_display': summary_topic.title,
                    'articles': all_chapters_data,
                    'checkpoint_part': part,
                    'checkpoint_type': type,
                    'is_dynamic': True,
                    'is_summary': True,
                    'topic_group': topic_group.title,
                    'summary_topic': summary_topic.title,
                    'summary_description': summary_topic.description,
                    'main_topics_count': main_topics.count()
                })
            
            else:
                # Fall back to using regular main topics
                main_topics = topic_group.topics.all().order_by('id')
                
                if type_index >= main_topics.count():
                    return HttpResponseForbidden("Invalid topic")
                
                main_topic = main_topics[type_index]
                
                # Get chapters for this main topic
                chapters = main_topic.chapters.all().order_by('order')
                
                # Prepare chapters data
                chapters_data = []
                
                for chapter in chapters:
                    chapters_data.append({
                        'number': chapter.order,
                        'title': chapter.title,
                        'explanation': chapter.content,
                        'is_header': False
                    })
                
                # Return JSON response with dynamic topic info
                type_display = main_topic.title
                
                return JsonResponse({
                    'part': part,
                    'type': type,
                    'type_display': type_display,
                    'articles': chapters_data,
                    'checkpoint_part': part,
                    'checkpoint_type': type,
                    'is_dynamic': True,
                    'is_summary': False,
                    'topic_group': topic_group.title,
                    'main_topic': main_topic.title
                })
            
        except Exception as e:
            print(f"Error loading dynamic topic content: {e}")
            # Fall back to standard articles if there's an error
            pass
    
    # Get articles for this checkpoint (legacy approach)
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
        'checkpoint_type': type,
        'is_dynamic': False
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
    
    # First check if we're using dynamic topics
    active_topic_groups = ActiveTopicGroups.get_active_groups()
    is_dynamic = active_topic_groups.exists()
    
    context = {}
    
    if is_dynamic:
        try:
            # Check if a summary topic ID was specified
            summary_topic_id = request.GET.get('summary_id')
            
            # Get the topic group based on part number (5 or 6)
            topic_group_index = part - 5
            if topic_group_index < 0 or topic_group_index >= active_topic_groups.count():
                return HttpResponseForbidden("Invalid topic group")
            
            active_group = active_topic_groups[topic_group_index]
            topic_group = active_group.topic_group
            
            if summary_topic_id:
                # User clicked on a summary topic
                try:
                    summary_topic = SummaryTopic.objects.get(id=summary_topic_id, topic_group=topic_group)
                    
                    # Get the main topics from this summary topic
                    main_topics_in_summary = summary_topic.main_topics.all().order_by('id')
                    
                    # Get all chapters from all main topics
                    all_chapters = []
                    for main_topic in main_topics_in_summary:
                        # Add the chapters with a reference to their main topic
                        for chapter in main_topic.chapters.all().order_by('order'):
                            chapter.parent_topic = main_topic.title  # Add parent topic info
                            all_chapters.append(chapter)
                    
                    # Prepare context
                    context = {
                        'is_dynamic': True,
                        'is_summary': True,
                        'topic_group': topic_group,
                        'summary_topic': summary_topic,
                        'main_topics': main_topics_in_summary,
                        'chapters': all_chapters,
                        'part': part,
                        'type': type,
                        'type_name': summary_topic.title,
                        'player_points': player_points
                    }
                    
                    return render(request, 'plat/article_details.html', context)
                    
                except SummaryTopic.DoesNotExist:
                    # Fall back to standard approach if summary topic not found
                    pass
            
            # Check if summary topics exist for this topic group
            summary_topics = SummaryTopic.objects.filter(topic_group=topic_group).order_by('order')
            
            # Get the type index based on JUD/LEG/EXEC
            type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(type, 0)
            
            if summary_topics.exists() and type_index < summary_topics.count():
                # Use summary topic
                summary_topic = summary_topics[type_index]
                
                # Get the main topics from this summary topic
                main_topics_in_summary = summary_topic.main_topics.all().order_by('id')
                
                # Get all chapters from all main topics
                all_chapters = []
                for main_topic in main_topics_in_summary:
                    # Add the chapters with a reference to their main topic
                    for chapter in main_topic.chapters.all().order_by('order'):
                        chapter.parent_topic = main_topic.title  # Add parent topic info
                        all_chapters.append(chapter)
                
                # Prepare context
                context = {
                    'is_dynamic': True,
                    'is_summary': True,
                    'topic_group': topic_group,
                    'summary_topic': summary_topic,
                    'main_topics': main_topics_in_summary,
                    'chapters': all_chapters,
                    'part': part,
                    'type': type,
                    'type_name': summary_topic.title,
                    'player_points': player_points
                }
                
                return render(request, 'plat/article_details.html', context)
            
            else:
                # Fall back to standard main topic
                # Map the part and type to a topic group and main topic (same as in checkpoint_detail)
                main_topics = topic_group.topics.all().order_by('id')
                
                if type_index >= main_topics.count():
                    return HttpResponseForbidden("Invalid topic")
                
                main_topic = main_topics[type_index]
                
                # Get chapters for this main topic
                chapters = main_topic.chapters.all().order_by('order')
                
                # Prepare context
                context = {
                    'is_dynamic': True,
                    'is_summary': False,
                    'topic_group': topic_group,
                    'main_topic': main_topic,
                    'chapters': chapters,
                    'part': part,
                    'type': type,
                    'type_name': main_topic.title, 
                    'player_points': player_points
                }
                
                return render(request, 'plat/article_details.html', context)
                
        except Exception as e:
            print(f"Error loading dynamic topic content for details page: {e}")
            # Fall back to standard articles if there's an error
            is_dynamic = False
    
    # Traditional article loading (for fallback)
    if not is_dynamic:
        # Get articles for this checkpoint
        articles = ConstitutionalArticle.objects.filter(
            part=part,
            type=type
        ).order_by('article_number')
        
        # Get bookmark for this user if exists
        try:
            bookmark = ArticleBookmark.objects.get(user=request.user)
            has_bookmark = True
        except ArticleBookmark.DoesNotExist:
            bookmark = None
            has_bookmark = False
        
        # Prepare type name
        type_names = {
            'JUD': 'Judiciary',
            'LEG': 'Legislative',
            'EXEC': 'Executive'
        }
        
        # Prepare context
        context = {
            'articles': articles,
            'part': part,
            'type': type,
            'type_name': type_names.get(type, type),
            'bookmark': bookmark,
            'has_bookmark': has_bookmark,
            'player_points': player_points,
            'is_dynamic': False
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

