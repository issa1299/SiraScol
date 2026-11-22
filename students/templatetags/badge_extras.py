from django import template
from core.badge import title_words

register = template.Library()


@register.filter
def capwords(value):
    """« baba toure » -> « Baba Toure », accents conservés."""
    return title_words(value)
