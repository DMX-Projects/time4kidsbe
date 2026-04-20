"""
JWT auth that does not hard-fail public endpoints when an optional Bearer token is bad.

DRF runs authenticators before permissions: the default JWTAuthentication raises
AuthenticationFailed on expired/invalid tokens or missing users, so AllowAny()
never runs. Treat those as unauthenticated so anonymous clients (and clients
with stale Authorization headers) can still hit public APIs.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenBackendError, TokenError


class LenientJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None
        try:
            return super().authenticate(request)
        except (TokenError, TokenBackendError, AuthenticationFailed):
            return None
