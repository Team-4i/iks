from django.core.management.base import BaseCommand
from spinwheel.models import PlayerCollection, UserCard

class Command(BaseCommand):
    help = 'Migrates data from PlayerCollection to UserCard'

    def handle(self, *args, **kwargs):
        collections = PlayerCollection.objects.all()
        for collection in collections:
            user_card, created = UserCard.objects.get_or_create(
                user=collection.player.user,
                card=collection.card,
                defaults={'quantity': collection.quantity}
            )
            if not created:
                user_card.quantity = collection.quantity
                user_card.save()
            self.stdout.write(f'Migrated {collection.card.title} for {collection.player.user.username}') 