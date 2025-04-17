from django import template

register = template.Library()

@register.filter
def count_key_points(content_points):
    """Count items in a list of content points where is_key_point is True"""
    return sum(1 for point in content_points if getattr(point, 'is_key_point', False)) 