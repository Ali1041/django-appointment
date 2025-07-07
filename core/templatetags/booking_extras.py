from django import template

register = template.Library()


@register.filter
def sub(value, arg):
    return float(value) - float(arg)


@register.filter
def currency(value):
    """
    Formats a number as a US dollar currency string.
    e.g. 1234.56 -> $1,234.56
    """
    try:
        value = float(value)
        return "${:,.2f}".format(value)
    except (ValueError, TypeError):
        return value
