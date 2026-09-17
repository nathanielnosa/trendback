from django.urls import path

from .views import *


urlpatterns = [

    path("register/",RegisterView.as_view(),name="register"),
    path("login/",LoginView.as_view(),name="login"),

    path("refresh/",RefreshTokenView.as_view(),name="refresh"),

    path("logout/",LogoutView.as_view(),name="logout"),

    path("me/",MeView.as_view(),name="me"),

    path("change-password/",ChangePasswordView.as_view(),name="change-password"),

    path("verify-email/",VerifyEmailView.as_view(),name="verify-email"),

    path("resend-verification/",ResendVerificationView.as_view(),name="resend-verification"),

    path("forgot-password/",ForgotPasswordView.as_view(),name="forgot-password"),

    path("reset-password/",ResetPasswordView.as_view(),name="reset-password"),
]