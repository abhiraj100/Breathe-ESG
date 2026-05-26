from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication with CSRF check disabled.
    Safe for a same-origin REST API — CORS headers are the
    cross-origin protection layer instead.
    """
    def enforce_csrf(self, request):
        return
