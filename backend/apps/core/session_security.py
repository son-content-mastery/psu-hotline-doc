from importlib import import_module

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone


def invalidate_user_sessions(user_id):
    """Delete active server-side sessions belonging to one user."""
    session_store = import_module(settings.SESSION_ENGINE).SessionStore
    deleted = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()).iterator():
        try:
            payload = session_store(session_key=session.session_key).load()
        except Exception:
            continue
        if str(payload.get("_auth_user_id", "")) == str(user_id):
            session.delete()
            deleted += 1
    return deleted
