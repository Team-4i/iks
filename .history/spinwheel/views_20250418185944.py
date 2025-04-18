from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import PlayerProfile, Card, PlayerCollection, UserCard, SpinResult, CardCombo, PlayerComboProgress
import random
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.shortcuts import redirect
from django.db.models import Count
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Q

@login_required
def index(request):
    profile, created = PlayerProfile.objects.get_or_create(user=request.user)
    
    # Check for new spins
    profile.check_and_add_spins()
    
    # Get time until next spin
    time_until_next = profile.time_until_next_spin()
    seconds_until_next = int(time_until_next.total_seconds()) if time_until_next else None
    
    # Get all player's collected cards
    collection = PlayerCollection.objects.filter(
        player=profile
    ).select_related('card').order_by('card__rarity', 'card__title')
    
    # Get the user's past wins (latest 3 wins)
    past_wins = SpinResult.objects.filter(user=request.user).order_by('-created_at')[:3].values(
        'type',
        'rarity',
        'description'
    )

    context = {
        'profile': profile,
        'collection': collection,
        'past_wins': past_wins,
        'seconds_until_next': seconds_until_next,
    }
    
    return render(request, 'spinwheel/index.html', context)

@login_required
@require_POST
def spin(request):
    profile = PlayerProfile.objects.get(user=request.user)
    
    # If no spins remaining, refill them
    if profile.spins_remaining <= 0:
        profile.refill_spins()
    
    # Try to use a spin
    if not profile.use_spin():
        return JsonResponse({
            'error': 'No spins remaining'
        }, status=400)
    
    # Updated rewards with more focus on cards
    rewards = [
        # Cards (70% total probability)
        {'type': 'card', 'rarity': 'COMMON', 'probability': 40, 'label': 'Common Card'},
        {'type': 'card', 'rarity': 'RARE', 'probability': 20, 'label': 'Rare Card'},
        {'type': 'card', 'rarity': 'EPIC', 'probability': 10, 'label': 'Epic Card'},
        # Coins (30% total probability)
        {'type': 'coin', 'amount': 10, 'probability': 15, 'label': '10 Coins'},
        {'type': 'coin', 'amount': 20, 'probability': 10, 'label': '20 Coins'},
        {'type': 'coin', 'amount': 50, 'probability': 5, 'label': '50 Coins'},
    ]
    
    # Select reward based on probability
    total = sum(r['probability'] for r in rewards)
    r = random.uniform(0, total)
    cumsum = 0
    for reward in rewards:
        cumsum += reward['probability']
        if r <= cumsum:
            selected_reward = reward
            break
    
    # Process reward
    if selected_reward['type'] == 'coin':
        profile.coins += selected_reward['amount']
        profile.save()
        reward_detail = f"{selected_reward['amount']} Coins"
        
        
        # Create a record of the coin win
        SpinResult.objects.create(
            user=request.user,
            type='COINS',
            rarity=None,
            description=reward_detail
        )
    else:
        # Get random card of selected rarity
        cards = Card.objects.filter(rarity=selected_reward['rarity'])
        if cards.exists():
            card = random.choice(cards)
            
            # Try to get existing collection or create new one
            collection, created = PlayerCollection.objects.get_or_create(
                player=profile,
                card=card,
                defaults={'quantity': 1}
            )
            
            if not created:
                collection.quantity += 1
                collection.save()
            
            reward_detail = f"{card.rarity} Card: {card.title}"
            
            # Add some bonus coins for collecting cards
            bonus_coins = {
                'COMMON': 5,
                'RARE': 15,
                'EPIC': 30
            }
            profile.coins += bonus_coins[card.rarity]
            profile.save()
            reward_detail += f" (+{bonus_coins[card.rarity]} Coins)"
            
            # Create a record of the card win
            SpinResult.objects.create(
                user=request.user,
                type='CARD',
                rarity=card.rarity,
                description=f"{card.title}"
            )
    
    return JsonResponse({
        'success': True,
        'reward': selected_reward,
        'reward_detail': reward_detail,
        'spins_remaining': profile.spins_remaining,
        'coins': profile.coins,
        'should_refresh': True
    })

def collection(request):
    if not request.user.is_authenticated:
        return redirect('account_login')
        
    collection = PlayerCollection.objects.filter(player__user=request.user).select_related('card')
    return render(request, 'spinwheel/collection.html', {
        'collection': collection
    })

def get_card_price(rarity):
    prices = {
        'COMMON': 100,
        'RARE': 250,
        'EPIC': 500
    }
    return prices.get(rarity, 0)

@login_required
def marketplace(request):
    # Get user profile for displaying coins
    user_profile = PlayerProfile.objects.get(user=request.user)
    
    # Only send minimal data to the template - actual cards will be loaded via AJAX
    return render(request, 'spinwheel/marketplace.html', {
        'profile': user_profile
    })

@login_required
def marketplace_items(request):
    page = int(request.GET.get('page', 1))
    items_per_page = 12  # Number of cards per page
    rarity_filter = request.GET.get('rarity', 'all')
    search_query = request.GET.get('search', '')
    
    # Get all cards
    cards_query = Card.objects.all()
    
    # Apply rarity filter if not 'all'
    if rarity_filter != 'all':
        cards_query = cards_query.filter(rarity__iexact=rarity_filter)
    
    # Apply search filter if provided
    if search_query:
        cards_query = cards_query.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query)
        )
    
    # Calculate pagination
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    total_items = cards_query.count()
    
    # Get paginated cards
    paginated_cards = cards_query[start_index:end_index]
    
    # Prepare data for template
    user_profile = PlayerProfile.objects.get(user=request.user)
    player_collections = PlayerCollection.objects.filter(player=user_profile)
    
    marketplace_items = []
    for card in paginated_cards:
        player_collection = player_collections.filter(card=card).first()
        marketplace_items.append({
            'card': {
                'id': card.id,
                'title': card.title,
                'content': card.content,
                'article_number': card.article_number,
                'rarity': card.rarity
            },
            'owned_quantity': player_collection.quantity if player_collection else 0,
            'price': get_card_price(card.rarity),
            'can_sell': player_collection.quantity > 1 if player_collection else False,
            'can_buy': user_profile.coins >= get_card_price(card.rarity)
        })
    
    return JsonResponse({
        'items': marketplace_items,
        'has_more': end_index < total_items,
        'total_items': total_items
    })

@login_required
def sell_card(request, card_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)

    try:
        user_profile = PlayerProfile.objects.get(user=request.user)
        player_collection = PlayerCollection.objects.get(player=user_profile, card_id=card_id)
        
        if player_collection.quantity <= 1:
            return JsonResponse({'error': 'Must keep at least one copy'}, status=400)

        # Get sell price and update balances
        sell_price = get_card_price(player_collection.card.rarity)
        
        player_collection.quantity -= 1
        player_collection.save()
        
        user_profile.coins += sell_price
        user_profile.save()

        return JsonResponse({
            'success': True,
            'new_quantity': player_collection.quantity,
            'coins': user_profile.coins
        })
    except PlayerCollection.DoesNotExist:
        return JsonResponse({'error': 'Card not found'}, status=404)

@login_required
def buy_card(request, card_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)

    try:
        card = Card.objects.get(id=card_id)
        price = get_card_price(card.rarity)
        user_profile = PlayerProfile.objects.get(user=request.user)

        if user_profile.coins < price:
            return JsonResponse({'error': 'Not enough coins'}, status=400)

        # Update player's card collection
        player_collection, created = PlayerCollection.objects.get_or_create(
            player=user_profile,
            card=card,
            defaults={'quantity': 0}
        )
        player_collection.quantity += 1
        player_collection.save()

        # Deduct coins
        user_profile.coins -= price
        user_profile.save()

        return JsonResponse({
            'success': True,
            'new_quantity': player_collection.quantity,
            'coins': user_profile.coins
        })
    except Card.DoesNotExist:
        return JsonResponse({'error': 'Card not found'}, status=404)

@login_required
def leaderboard(request):
    print("\n=== Debugging from Spinwheel: leaderboard view ===")
    
    # Get only users who have PlayerProfile
    all_users = User.objects.filter(playerprofile__isnull=False)
    leaderboard = []
    user_rank = None
    
    for rank, user in enumerate(all_users, 1):
        # Get card count from PlayerCollection
        card_count = PlayerCollection.objects.filter(
            player__user=user,
            quantity__gt=0  # Only count cards they actually have
        ).count()
        
        print(f"User {user.username} has {card_count} unique cards")
        
        entry = {
            'rank': rank,
            'user': user,
            'card_count': card_count
        }
        leaderboard.append(entry)
        
        # Store user's rank for highlighting
        if user == request.user:
            user_rank = entry.copy()
    
    # Sort by coins (primary) and card count (secondary)
    leaderboard.sort(key=lambda x: (-x['user'].playerprofile.coins, -x['card_count']))
    
    # Reassign ranks after sorting
    for rank, entry in enumerate(leaderboard, 1):
        entry['rank'] = rank
        if entry['user'] == request.user:
            user_rank['rank'] = rank
    
    # Get top 3 players from sorted leaderboard
    top_players = [entry['user'] for entry in leaderboard[:3]] if leaderboard else []
    
    if top_players:
        print(f"Top player: {top_players[0].username} with {leaderboard[0]['card_count']} cards")
    
    # Create PlayerProfile for current user if doesn't exist
    if not hasattr(request.user, 'playerprofile'):
        PlayerProfile.objects.create(user=request.user)
    
    return render(request, 'spinwheel/leaderboard.html', {
        'top_players': top_players,
        'leaderboard': leaderboard[:50],  # Show top 50 players
        'user_rank': user_rank
    })

@login_required
def card_combos(request):
    profile = PlayerProfile.objects.get(user=request.user)
    combos = CardCombo.objects.all()
    player_progress = PlayerComboProgress.objects.filter(player=profile)

    # Check for completed combos
    for progress in player_progress:
        if not progress.is_completed:
            required_cards = progress.combo.required_cards.all()
            player_cards = PlayerCollection.objects.filter(player=profile, card__in=required_cards)
            if player_cards.count() == required_cards.count():
                progress.is_completed = True
                profile.coins += progress.combo.bonus_coins
                profile.save()
                progress.save()

    return render(request, 'spinwheel/card_combos.html', {
        'combos': combos,
        'player_progress': player_progress,
    })

def spinwheel_intro(request):
    return render(request, 'spinwheel/intro.html')

def get_random_card():
    # Define rarity probabilities
    rarity_weights = {
        'COMMON': 70,
        'RARE': 25,
        'EPIC': 5
    }
    
    # First, select rarity based on weights
    rarity = random.choices(
        list(rarity_weights.keys()),
        weights=list(rarity_weights.values())
    )[0]
    
    # Then get a random card of that rarity
    cards = Card.objects.filter(rarity=rarity)
    if not cards.exists():
        return None
    
    return random.choice(cards)

@receiver([post_save, post_delete], sender=PlayerCollection)
def update_platform_stats(sender, instance, **kwargs):
    """Update platform stats whenever a PlayerCollection is modified"""
    try:
        from plat.models import PlayerPlatPoints
        plat_points = PlayerPlatPoints.objects.get(player=instance.player.user)
        plat_points.update_spinwheel_stats()
    except Exception as e:
        print(f"Error updating platform stats: {e}")