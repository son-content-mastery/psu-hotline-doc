from django.urls import path

from . import views


urlpatterns = [
    path("auth/me/", views.AuthMeView.as_view(), name="auth-me"),
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/activation/resend/", views.ActivationResendView.as_view(), name="auth-activation-resend"),
    path("auth/activation/confirm/", views.ActivationConfirmView.as_view(), name="auth-activation-confirm"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password-reset/", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("classification/questions/", views.ClassificationQuestionsView.as_view(), name="classification-questions"),
    path("classification/evaluate/", views.ClassificationEvaluateView.as_view(), name="classification-evaluate"),
    path("locations/phuket/", views.PhuketLocationCatalogView.as_view(), name="phuket-locations"),
    path("local-authorities/", views.LocalAuthorityListView.as_view(), name="local-authorities"),
    path("property-types/", views.PropertyTypeListView.as_view(), name="property-types"),
    path(
        "property-types/<int:pk>/requirements/",
        views.PublicPropertyTypeRequirementsView.as_view(),
        name="public-property-type-requirements",
    ),
    path("applications/", views.ApplicationListCreateView.as_view(), name="applications"),
    path("applications/<int:pk>/", views.ApplicationDetailView.as_view(), name="application-detail"),
    path(
        "applications/<int:pk>/requirements/",
        views.ApplicationRequirementsView.as_view(),
        name="application-requirements",
    ),
    path("applications/<int:pk>/submit/", views.ApplicationSubmitView.as_view(), name="application-submit"),
    path("applications/<int:pk>/history/", views.ApplicationHistoryView.as_view(), name="application-history"),
    path("applications/<int:pk>/documents/", views.ApplicationDocumentsView.as_view(), name="application-documents"),
    path(
        "applications/<int:pk>/documents/<int:document_id>/file/",
        views.ApplicantDocumentFileView.as_view(),
        name="applicant-document-file",
    ),
    path("applications/<int:pk>/license/", views.ApplicationLicenseView.as_view(), name="application-license"),
    path("officer/applications/", views.OfficerApplicationListView.as_view(), name="officer-applications"),
    path(
        "officer/applications/<int:pk>/",
        views.OfficerApplicationDetailView.as_view(),
        name="officer-application-detail",
    ),
    path(
        "officer/documents/<int:pk>/review/",
        views.OfficerDocumentReviewView.as_view(),
        name="officer-document-review",
    ),
    path(
        "officer/documents/<int:pk>/file/",
        views.OfficerDocumentFileView.as_view(),
        name="officer-document-file",
    ),
    path(
        "officer/applications/<int:pk>/approve/",
        views.OfficerApproveView.as_view(),
        name="officer-approve",
    ),
    path(
        "officer/applications/<int:pk>/request-revision/",
        views.OfficerRequestRevisionView.as_view(),
        name="officer-request-revision",
    ),
    path(
        "officer/applications/<int:pk>/reject/",
        views.OfficerRejectView.as_view(),
        name="officer-reject",
    ),
    path("central/summary/", views.CentralSummaryView.as_view(), name="central-summary"),
]
