from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

class Card(models.Model):
    RARITY_CHOICES = [
        ('COMMON', 'Common'),
        ('RARE', 'Rare'),
        ('EPIC', 'Epic'),
    ]
    
    title = models.CharField(max_length=200)
    article_number = models.CharField(max_length=50)
    content = models.TextField()
    rarity = models.CharField(max_length=10, choices=RARITY_CHOICES)
    base_price = models.IntegerField(default=100)
    
    class Meta:
        unique_together = ['article_number', 'rarity']
    
    def get_market_price(self):
        multipliers = {
            'COMMON': 1,
            'RARE': 3,
            'EPIC': 10
        }
        return self.base_price * multipliers[self.rarity]
    
    def __str__(self):
        return f"{self.article_number} - {self.title} ({self.rarity})"

class PlayerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    coins = models.IntegerField(default=0)
    spins_remaining = models.IntegerField(default=10)
    max_spins = models.IntegerField(default=10)
    last_spin_refill = models.DateTimeField(auto_now_add=True)
    
    def time_until_next_spin(self):
        if self.spins_remaining >= self.max_spins:
            return None
        
        next_spin_time = self.last_spin_refill + timedelta(minutes=1)
        time_left = next_spin_time - timezone.now()
        return time_left if time_left.total_seconds() > 0 else timedelta(0)
    
    def check_and_add_spins(self):
        if self.spins_remaining >= self.max_spins:
            return False
            
        time_since_last = timezone.now() - self.last_spin_refill
        minutes_passed = time_since_last.total_seconds() / 60
        spins_to_add = min(int(minutes_passed), self.max_spins - self.spins_remaining)
        
        if spins_to_add > 0:
            self.spins_remaining += spins_to_add
            self.last_spin_refill = timezone.now()
            self.save()
            return True
        return False

    def use_spin(self):
        self.check_and_add_spins()
        if self.spins_remaining > 0:
            self.spins_remaining -= 1
            self.last_spin_refill = timezone.now()
            self.save()
            return True
        return False

class PlayerCollection(models.Model):
    player = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Move platform stats update to post_save signal
        
    class Meta:
        unique_together = ('player', 'card')

class UserCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = ['user', 'card']

    def __str__(self):
        return f"{self.user.username} - {self.card.title} (×{self.quantity})"

class SpinResult(models.Model):
    RESULT_TYPES = [
        ('CARD', 'Card'),
        ('COINS', 'Coins'),
    ]
    
    RARITY_CHOICES = [
        ('COMMON', 'Common'),
        ('RARE', 'Rare'),
        ('EPIC', 'Epic'),
        ('LEGENDARY', 'Legendary'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=RESULT_TYPES)
    rarity = models.CharField(max_length=10, choices=RARITY_CHOICES, null=True, blank=True)
    description = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class CardCombo(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    required_cards = models.ManyToManyField(Card)
    bonus_coins = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class PlayerComboProgress(models.Model):
    player = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE)
    combo = models.ForeignKey(CardCombo, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('player', 'combo')

@receiver([post_save], sender=PlayerProfile)
def update_coins_in_platform(sender, instance, **kwargs):
    """Update coins in platform whenever PlayerProfile is modified"""
    try:
        from plat.models import PlayerPlatPoints
        plat_points = PlayerPlatPoints.objects.get(player=instance.user)
        plat_points.spinwheel_coins = instance.coins
        plat_points.save()
    except Exception as e:
        print(f"Error updating platform coins: {e}")

@receiver([post_save, post_delete], sender=PlayerCollection)
def update_card_stats(sender, instance, **kwargs):
    """Update card statistics whenever PlayerCollection is modified"""
    try:
        from plat.models import PlayerPlatPoints
        
        # Get the player's platform points
        plat_points = PlayerPlatPoints.objects.get(player=instance.player.user)
        
        # Get all collections for this player
        collections = PlayerCollection.objects.filter(player=instance.player)
        
        # Reset counters
        common = rare = epic = 0
        
        # Count unique cards by rarity
        for collection in collections:
            if collection.quantity > 0:  # Only count if player has the card
                if collection.card.rarity == 'COMMON':
                    common += 1  # Count unique cards, not quantities
                elif collection.card.rarity == 'RARE':
                    rare += 1
                elif collection.card.rarity == 'EPIC':
                    epic += 1
        
        # Update platform stats
        plat_points.common_cards = common
        plat_points.rare_cards = rare
        plat_points.epic_cards = epic
        plat_points.total_cards = common + rare + epic
        
        # Also update coins
        plat_points.spinwheel_coins = instance.player.coins
        
        plat_points.save()
        
    except Exception as e:
        print(f"Error updating card stats: {e}")
