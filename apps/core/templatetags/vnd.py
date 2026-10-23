from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def vnd(value):
    """40000 -> 40.000đ"""
    try:
        number = int(Decimal(value).quantize(Decimal("1")))
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{number:,}".replace(",", ".") + "đ"