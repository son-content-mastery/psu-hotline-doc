from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    """Django session authentication with an explicit 401 challenge."""

    def authenticate_header(self, request):
        return "Session"
