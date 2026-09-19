import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.core.models import LocalAuthority, User


@pytest.fixture
def seeded(db, settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    monkeypatch.setenv("DEMO_PASSWORD", "DemoPass123!")
    call_command("seed_demo", verbosity=0)
    return {
        "applicant": User.objects.get(email="applicant@example.test"),
        "officer": User.objects.get(email="officer.patong@example.test"),
        "central": User.objects.get(email="central@example.test"),
        "admin": User.objects.get(email="admin@example.test"),
        "patong": LocalAuthority.objects.get(code="PATONG_MUNICIPALITY"),
    }


@pytest.fixture
def api_client():
    return APIClient()
