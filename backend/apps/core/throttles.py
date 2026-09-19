import hashlib

from rest_framework.throttling import SimpleRateThrottle


class AccountEmailRateThrottle(SimpleRateThrottle):
    """Throttle account-email actions without storing a raw address in cache keys."""

    scope = "account_email"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return None
        digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}
