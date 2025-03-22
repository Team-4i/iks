from django.core.management.base import BaseCommand
from snake_ladder.models import Cell, CellContent
from django.db import transaction
import random

class Command(BaseCommand):
    help = 'Sets up cells and distributes content for the Snake & Ladder game'

    def reset_and_create_cells(self):
        """Delete all cells and recreate them with proper types"""
        try:
            # Delete all existing cells
            Cell.objects.all().delete()
            
            # Snake-ladder cells
            SNAKE_LADDER_CELLS = [
                8, 15, 24, 28, 
                31, 37, 45, 49,
                52, 58, 61, 67,
                74, 78, 82, 85,
                91, 94, 97, 100
            ]
            
            # Create all cells (1-100)
            with transaction.atomic():
                for number in range(1, 101):
                    cell_type = 'SNAKE_LADDER' if number in SNAKE_LADDER_CELLS else 'NORMAL'
                    Cell.objects.create(
                        number=number,
                        cell_type=cell_type
                    )
            
            self.stdout.write(self.style.SUCCESS("Successfully created all cells!"))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating cells: {str(e)}"))
            return False

    def distribute_content(self):
        """Distribute CellContent to normal cells"""
        try:
            # Get all normal cells
            normal_cells = Cell.objects.filter(cell_type='NORMAL')
            
            # Get content grouped by part and type
            content_groups = {
                5: {
                    'JUD': list(CellContent.objects.filter(part=5, type='JUD')),
                    'LEG': list(CellContent.objects.filter(part=5, type='LEG')),
                    'EXEC': list(CellContent.objects.filter(part=5, type='EXEC'))
                },
                6: {
                    'JUD': list(CellContent.objects.filter(part=6, type='JUD')),
                    'LEG': list(CellContent.objects.filter(part=6, type='LEG')),
                    'EXEC': list(CellContent.objects.filter(part=6, type='EXEC'))
                }
            }
            
            with transaction.atomic():
                # Clear all existing content associations
                for cell in normal_cells:
                    cell.contents.clear()
                    cell.current_content = None
                    cell.save()
                
                # Distribute content to each normal cell
                for cell in normal_cells:
                    for part in [5, 6]:
                        for type_ in ['JUD', 'LEG', 'EXEC']:
                            content_list = content_groups[part][type_]
                            if content_list:
                                # Get a random content and remove it from the list
                                content = random.choice(content_list)
                                content_list.remove(content)
                                cell.contents.add(content)
            
            self.stdout.write(self.style.SUCCESS("Successfully distributed content!"))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error distributing content: {str(e)}"))
            return False

    def randomly_set_current_content(self):
        """Set random current_content for each normal cell"""
        try:
            normal_cells = Cell.objects.filter(cell_type='NORMAL')
            
            with transaction.atomic():
                for cell in normal_cells:
                    available_content = cell.contents.all()
                    if available_content:
                        cell.current_content = random.choice(available_content)
                        cell.save()
            
            self.stdout.write(self.style.SUCCESS("Successfully set random current content!"))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error setting current content: {str(e)}"))
            return False

    def handle(self, *args, **options):
        self.stdout.write("Starting cell setup process...")
        
        if self.reset_and_create_cells():
            self.stdout.write(self.style.SUCCESS("Step 1: Cells created successfully"))
            
            if self.distribute_content():
                self.stdout.write(self.style.SUCCESS("Step 2: Content distributed successfully"))
                
                if self.randomly_set_current_content():
                    self.stdout.write(self.style.SUCCESS("Step 3: Current content set successfully"))
                    self.stdout.write(self.style.SUCCESS("Setup completed successfully!"))
                    return
        
        self.stdout.write(self.style.ERROR("Setup failed!"))