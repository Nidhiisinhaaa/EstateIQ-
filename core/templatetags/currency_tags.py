from django import template

register = template.Library()


@register.filter
def inr(value):
    """Format a rupee amount using the Indian lakh/crore convention, e.g. 1,23,45,000."""
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return value
    negative = value < 0
    value = abs(value)
    s = str(value)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted = ",".join(groups) + "," + last3
    return ("-" if negative else "") + "₹" + formatted


@register.filter
def inr_short(value):
    """Format a rupee amount as a short crore/lakh label, e.g. 1.24 Cr or 45.0 L."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_00_00_000:
        return f"{sign}{value / 1_00_00_000:.2f} Cr"
    if value >= 1_00_000:
        return f"{sign}{value / 1_00_000:.2f} L"
    return f"{sign}{value:,.0f}"
