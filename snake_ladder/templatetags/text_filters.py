from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Template filter to get dictionary value by key"""
    return dictionary.get(str(key)) 