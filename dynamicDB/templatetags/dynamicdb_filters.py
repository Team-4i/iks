from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using its key
    Usage: {{ mydict|get_item:key_variable }}
    or nested: {{ mydict|get_item:key1|get_item:key2 }}
    """
    if dictionary is None:
        return None
        
    if hasattr(dictionary, 'get'):
        # Dictionary-like object
        return dictionary.get(key)
    elif hasattr(dictionary, key):
        # Object with attributes
        return getattr(dictionary, key)
    else:
        # Try using key as index
        try:
            return dictionary[key]
        except (KeyError, TypeError, IndexError):
            return None

@register.filter
def split(value, arg):
    """
    Split a string by the given separator
    Usage: {{ "a,b,c"|split:"," }} -> ['a', 'b', 'c']
    """
    if value is None:
        return []
    
    if not isinstance(value, str):
        value = str(value)
        
    return value.split(arg) 