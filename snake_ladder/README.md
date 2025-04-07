# Standalone Snake & Ladder Game

This is a standalone version of the Snake & Ladder game that uses its own database of facts instead of relying on the platform's data.

## Setup Instructions

1. **Create the database tables**:
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Import facts from CSV**:
   ```
   python manage.py import_facts snake_ladder/facts.csv
   ```

3. **Run the server**:
   ```
   python manage.py runserver
   ```

## How It Works

### Data Structure

The game now uses a simple `GameFact` model to store constitutional law facts. These facts are displayed in the game cells and used to generate questions.

### Game Flow

1. When a player creates a game room, the system randomly selects facts from the `GameFact` model and assigns them to cells.
2. When a player lands on a cell, they see the fact associated with that cell.
3. When a player lands on a special cell (snake/ladder), they are presented with a question generated from a fact they've seen.
4. The game tracks points and progress independently of the platform.

### Adding More Facts

To add more facts to the game:

1. Add new facts to the `facts.csv` file.
2. Run the import command again:
   ```
   python manage.py import_facts snake_ladder/facts.csv
   ```

## Benefits of This Approach

- **Independence**: The game now operates independently of the platform's data system.
- **Simplicity**: The data structure is simple and focused on facts only.
- **Flexibility**: You can easily add, remove, or modify facts without affecting the platform.
- **Performance**: The game loads faster since it doesn't need to sync with the platform.

## Customization

You can customize the game by:

1. Modifying the `facts.csv` file to include your own facts.
2. Adjusting the game logic in `views.py` to change how facts are displayed or questions are generated.
3. Updating the UI templates to change the appearance of the game.