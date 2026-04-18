from django import template

register = template.Library()


@register.filter
def nrr_display(value):
    """Format NRR with + or - prefix."""
    try:
        val = float(value)
        if val > 0:
            return f"+{val:.3f}"
        elif val < 0:
            return f"{val:.3f}"
        else:
            return "0.000"
    except (ValueError, TypeError):
        return "0.000"


@register.filter
def is_qualified(rank, qualify_count=4):
    """Check if rank is within qualification zone."""
    try:
        return int(rank) <= int(qualify_count)
    except (ValueError, TypeError):
        return False


@register.filter
def percentage(value, total):
    """Calculate percentage."""
    try:
        if int(total) == 0:
            return 0
        return round(int(value) / int(total) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0
