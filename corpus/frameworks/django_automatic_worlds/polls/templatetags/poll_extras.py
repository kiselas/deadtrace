from django import template

register = template.Library()


@register.filter
def shout(value: str) -> str:
    return value.upper()
