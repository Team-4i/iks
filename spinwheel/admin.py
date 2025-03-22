from django.contrib import admin
from .models import Card, PlayerProfile, PlayerCollection, SpinResult, CardCombo, PlayerComboProgress

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('article_number', 'title', 'rarity', 'base_price')
    list_filter = ('rarity',)
    search_fields = ('title', 'article_number', 'content')
    ordering = ('rarity', 'article_number')

@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'coins', 'spins_remaining', 'max_spins', 'last_spin_refill')
    list_filter = ('max_spins',)
    search_fields = ('user__username',)
    readonly_fields = ('last_spin_refill',)
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Player'
    get_username.admin_order_field = 'user__username'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(PlayerCollection)
class PlayerCollectionAdmin(admin.ModelAdmin):
    list_display = ('get_player_name', 'get_card_title', 'quantity', 'get_rarity', 'get_article_number')
    list_filter = ('card__rarity',)
    search_fields = ('player__user__username', 'card__title', 'card__article_number')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('player', 'player__user', 'card')
    
    def get_player_name(self, obj):
        return obj.player.user.username
    get_player_name.short_description = 'Player'
    get_player_name.admin_order_field = 'player__user__username'
    
    def get_card_title(self, obj):
        return obj.card.title
    get_card_title.short_description = 'Card Title'
    get_card_title.admin_order_field = 'card__title'
    
    def get_rarity(self, obj):
        return obj.card.rarity
    get_rarity.short_description = 'Rarity'
    get_rarity.admin_order_field = 'card__rarity'
    
    def get_article_number(self, obj):
        return obj.card.article_number
    get_article_number.short_description = 'Article Number'
    get_article_number.admin_order_field = 'card__article_number'

@admin.register(SpinResult)
class SpinResultAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'type', 'rarity', 'description', 'created_at')
    list_filter = ('type', 'rarity', 'created_at')
    search_fields = ('user__username', 'description')
    readonly_fields = ('created_at',)
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Player'
    get_username.admin_order_field = 'user__username'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(CardCombo)
class CardComboAdmin(admin.ModelAdmin):
    list_display = ('name', 'bonus_coins', 'get_required_cards')
    search_fields = ('name', 'description')
    filter_horizontal = ('required_cards',)
    
    def get_required_cards(self, obj):
        return ", ".join([card.title for card in obj.required_cards.all()])
    get_required_cards.short_description = 'Required Cards'

@admin.register(PlayerComboProgress)
class PlayerComboProgressAdmin(admin.ModelAdmin):
    list_display = ('get_player_name', 'get_combo_name', 'is_completed')
    list_filter = ('is_completed',)
    search_fields = ('player__user__username', 'combo__name')
    
    def get_player_name(self, obj):
        return obj.player.user.username
    get_player_name.short_description = 'Player'
    get_player_name.admin_order_field = 'player__user__username'
    
    def get_combo_name(self, obj):
        return obj.combo.name
    get_combo_name.short_description = 'Combo'
    get_combo_name.admin_order_field = 'combo__name'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('player', 'player__user', 'combo')
