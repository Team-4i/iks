from django import template
from django.contrib.auth.models import User

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary safely."""
    if isinstance(dictionary, dict):
        try:
            if isinstance(key, str):
                return dictionary.get(int(key))
            return dictionary.get(key)
        except (ValueError, TypeError):
            return dictionary.get(key)
    return None