from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.SessionAuthentication401"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
            "description": "Django server-side session cookie. Unsafe requests also require X-CSRFToken.",
        }
