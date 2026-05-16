"""JWT from Authorization header or ?access= query (for opening files in a new tab)."""

from accounts.authentication import LenientJWTAuthentication


class QueryJWTAuthentication(LenientJWTAuthentication):
    """Allow Bearer token in query string so window.open() can load protected files."""

    def get_header(self, request):
        header = super().get_header(request)
        if header is not None:
            return header
        token = request.GET.get("access") or request.GET.get("token")
        if token:
            return f"Bearer {token}".encode("utf-8")
        return None
