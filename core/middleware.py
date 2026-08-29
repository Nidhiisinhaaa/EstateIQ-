"""
Hand-rolled Content-Security-Policy middleware (Phase 10). Allow-lists exactly the external
hosts the templates actually load from: Tailwind's CDN build, Chart.js and Leaflet + its
marker-cluster plugin off jsdelivr/unpkg, Google Fonts, and the CartoDB/OpenStreetMap map tiles.

'unsafe-inline' is required for both script-src and style-src because this project deliberately
has no JS/CSS build step (per the project's global rules) -- the Tailwind config, the map/chart
bootstrap variables, and a few inline style attributes (e.g. the confidence gauge's
conic-gradient) all live directly in template <script>/<style> blocks. Removing it would require
a nonce-per-request scheme threaded through every template, which is more machinery than this
project's scope calls for.
"""

from django.conf import settings


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.header_value = self._build_header()

    def _build_header(self) -> str:
        script_hosts = " ".join(settings.CSP_ALLOWED_SCRIPT_HOSTS)
        style_hosts = " ".join(settings.CSP_ALLOWED_STYLE_HOSTS)
        font_hosts = " ".join(settings.CSP_ALLOWED_FONT_HOSTS)
        img_hosts = " ".join(settings.CSP_ALLOWED_IMG_HOSTS)
        connect_hosts = " ".join(settings.CSP_ALLOWED_CONNECT_HOSTS)

        directives = [
            "default-src 'self'",
            f"script-src 'self' 'unsafe-inline' {script_hosts}",
            f"style-src 'self' 'unsafe-inline' {style_hosts}",
            f"font-src 'self' {font_hosts}",
            f"img-src 'self' data: {img_hosts}",
            f"connect-src 'self' {connect_hosts}",
            "frame-ancestors 'self'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        return "; ".join(directives)

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = self.header_value
        return response
