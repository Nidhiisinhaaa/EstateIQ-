from django.conf import settings


def site_meta(request):
    """Expose site-wide name/tagline to every template without repeating view boilerplate."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
    }
