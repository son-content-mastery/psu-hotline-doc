import pytest
from django.utils import timezone

from apps.core.models import User


@pytest.mark.django_db
def test_unverified_existing_session_cannot_use_role_protected_api(api_client):
    user = User.objects.create_user(
        email="unverified-session@example.test",
        password="StrongRegistrationPass123!",
        display_name="Unverified Applicant",
        role=User.Role.APPLICANT,
    )
    api_client.force_authenticate(user)

    response = api_client.get("/api/v1/applications/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_verified_user_can_use_role_protected_api(api_client):
    user = User.objects.create_user(
        email="verified-session@example.test",
        password="StrongRegistrationPass123!",
        display_name="Verified Applicant",
        role=User.Role.APPLICANT,
        email_verified_at=timezone.now(),
    )
    api_client.force_authenticate(user)

    response = api_client.get("/api/v1/applications/")

    assert response.status_code == 200
