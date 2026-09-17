import logging
from django.contrib.auth import authenticate
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import *
from .models import AuthToken,User
from .services import (create_auth_token,
                       send_verification_email,
                       get_token_hash,
                       send_password_reset_email,
                       rotate_refresh_token)

from .permissions import (
    IsAdmin,
    IsEditor,
    IsAuthor,
    IsContributor,
    IsSubscriber,
    CanCreatePost,
    CanPublishPost,
    CanReviewPost,
    CanManageUsers,
    CanViewAnalytics,
)

logger = logging.getLogger("backblog")


'''
================== **** ===============
================== CRUD ===============
================== **** ===============
'''
# :::: REGISTRATION
class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request,*args, **kwargs):

        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            raw_token, token = create_auth_token(user=user,
                purpose=AuthToken.Purpose.EMAIL_VERIFICATION,
                expiration_minutes=60
                )
            
            verification_url = (
                            f"http://localhost:5173/verify-email/?token={raw_token}"
                            )
            send_verification_email(user,verification_url)
            return Response(
                {
                    "message": "Account created successfully.",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    }
                },
                status=status.HTTP_201_CREATED
            )
        logger.info("User registered successfully: %s",user.email)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

# :::: EMAIL VERIFICATION AFTER REGISTRATION
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request,*args, **kwargs):
        raw_token = request.data.get("token")
        if not raw_token:

            return Response(
                {
                    "message":
                        "Verification token is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        token_hash = get_token_hash(raw_token)

        auth_token = AuthToken.objects.filter(
            token_hash=token_hash,
            purpose=AuthToken.Purpose.EMAIL_VERIFICATION
        ).select_related("user").first()

        if not auth_token:

            return Response(
                {
                    "message":
                        "Invalid verification token."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if auth_token.is_used:

            return Response(
                {
                    "message":
                        "This verification token has already been used."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if auth_token.is_expired:

            return Response(
                {
                    "message":
                        "This verification token has expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = auth_token.user

        user.is_verified = True

        user.save(
            update_fields=[
                "is_verified",
                "updated_at"
            ]
        )
        logger.info("Email verified successfully: %s",user.email)

        auth_token.used_at = timezone.now()

        auth_token.save(
            update_fields=["used_at"]
        )

        return Response(
            {
                "message":
                    "Email verified successfully."
            },
            status=status.HTTP_200_OK
        )

# :::: RESEND VERIFICATION
class ResendVerificationView(APIView):

    permission_classes = [AllowAny]

    def post(self, request,*args, **kwargs):

        email = request.data.get("email")

        if not email:

            return Response(
                {
                    "message":
                        "Email address is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email.lower().strip()).first()

        # Don't reveal whether an account exists.
        if not user:

            return Response(
                {
                    "message":
                        "If an account exists, a verification email will be sent."
                },
                status=status.HTTP_200_OK
            )

        if user.is_verified:

            return Response(
                {
                    "message":
                        "This account is already verified."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        raw_token, token = create_auth_token(
            user=user,
            purpose=AuthToken.Purpose.EMAIL_VERIFICATION,
            expiration_minutes=60
        )

        verification_url = (
            f"http://localhost:5173/verify-email/?token={raw_token}"
        )

        send_verification_email(
            user,
            verification_url
        )
        logger.info("Verification email requested: %s",user.email)
        return Response(
            {
                "message":
                    "If an account exists, a verification email will be sent."
            },
            status=status.HTTP_200_OK
        )

# :::: LOGIN
class LoginView(APIView):

    permission_classes = [AllowAny]
    def post(self, request,*args, **kwargs):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = authenticate(request=request,username=email,password=password)
        logger.info("User logged in successfully: %s",user.email,)
        if user is None:
            return Response(
                {
                    "message": "Invalid email or password."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        logger.warning("Failed login attempt: %s",email)

        if not user.is_active:
            return Response(
                {
                    "message": "Your account has been deactivated."
                },
                status=status.HTTP_403_FORBIDDEN
            )
        if not user.is_verified:
            return Response(
                {
                    "message":
                        "Please verify your email before logging in."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful.",
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_verified": user.is_verified,
                }
            },
            status=status.HTTP_200_OK
        )

# :::: FORGOT PASSWORD
class ForgotPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request,*args, **kwargs):

        email = request.data.get("email")

        if not email:

            return Response(
                {
                    "message":
                        "Email address is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(
            email=email.lower().strip()
        ).first()

        # Security: don't reveal account existence.
        if user:

            raw_token, token = create_auth_token(
                user=user,
                purpose=AuthToken.Purpose.PASSWORD_RESET,
                expiration_minutes=30
            )

            reset_url = (
                f"http://localhost:5173/reset-password/"
                f"?token={raw_token}"
            )

            send_password_reset_email(
                user,
                reset_url
            )
            logger.info("Password reset requested: %s",user.email)

        return Response(
            {
                "message":
                    "If an account exists with that email, "
                    "a password reset link has been sent."
            },
            status=status.HTTP_200_OK
        )

# ::: RESET PASSWORD
class ResetPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        serializer = ResetPasswordSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        raw_token = serializer.validated_data["token"]

        token_hash = get_token_hash(raw_token)

        auth_token = AuthToken.objects.filter(
            token_hash=token_hash,
            purpose=AuthToken.Purpose.PASSWORD_RESET
        ).select_related("user").first()

        if not auth_token:

            return Response(
                {
                    "message":
                        "Invalid password reset token."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if auth_token.is_used:

            return Response(
                {
                    "message":
                        "This password reset token has already been used."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if auth_token.is_expired:

            return Response(
                {
                    "message":
                        "This password reset token has expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = auth_token.user

        user.set_password(
            serializer.validated_data["new_password"]
        )

        user.save(
            update_fields=[
                "password",
                "updated_at"
            ]
        )
        logger.info("Password reset completed: %s", user.email)

        auth_token.used_at = timezone.now()

        auth_token.save(
            update_fields=["used_at"]
        )

        return Response(
            {
                "message":
                    "Password reset successfully."
            },
            status=status.HTTP_200_OK
        )

# :: REFRESH TOKEN
class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request,*args, **kwargs):

        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {
                    "message": "Refresh token is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            tokens = rotate_refresh_token(refresh_token)
            logger.info("Access token refreshed: %s",
            request.user.email if request.user.is_authenticated else "anonymous")
            return Response(
                {
                    "message": "Token refreshed successfully.",
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK
            )

        except TokenError:

            return Response(
                {
                    "message": "Invalid or expired refresh token."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        except User.DoesNotExist:

            return Response(
                {
                    "message": "User account no longer exists."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        except ValueError as error:

            return Response(
                {
                    "message": str(error)
                },
                status=status.HTTP_403_FORBIDDEN
            )

# :::: LOGOUT
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request,*args, **kwargs):

        refresh_token = request.data.get("refresh")

        if not refresh_token:

            return Response(
                {
                    "message": "Refresh token is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            token = RefreshToken(refresh_token)

            token.blacklist()
            logger.info("User logged out successfully: %s",request.user.email)

            return Response(
                {
                    "message": "Logout successful."
                },
                status=status.HTTP_200_OK
            )

        except TokenError:

            return Response(
                {
                    "message": "Invalid or expired refresh token."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

# USERS DASHBOARD/VIEW
class MeView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request,*args, **kwargs):

        user = request.user

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_verified": user.is_verified,
                "avatar": (
                    user.avatar.url
                    if user.avatar
                    else None
                ),
                "bio": user.bio,
                "date_joined": user.date_joined,
            },
            status=status.HTTP_200_OK
        )

# ::: CHANGE PASSWORD
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request,*args, **kwargs):

        serializer = ChangePasswordSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        current_password = serializer.validated_data["current_password"]

        new_password = serializer.validated_data["new_password"]

        if not user.check_password(current_password):

            return Response(
                {
                    "message": "Current password is incorrect."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if current_password == new_password:

            return Response(
                {
                    "message":
                        "New password must be different from current password."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)

        user.save(
            update_fields=[
                "password",
                "updated_at"
            ]
        )
        logger.info("Password changed successfully: %s",request.user.email)

        return Response(
            {
                "message": "Password changed successfully."
            },
            status=status.HTTP_200_OK
        )

# ============================================================
# SERVER ERROR TEST VIEW
# ============================================================
class ServerErrorTestView(APIView):
    """
    This endpoint intentionally raises an exception.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):

        raise Exception("This is a test server error.")
    
# ============================================================
# ROLE & PERMISSION TEST VIEWS
# ============================================================
class AdminPermissionTestView(APIView):
    permission_classes = [IsAdmin]
    def get(self, request):
        return Response(
            {
                "message": "Admin permission granted.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class EditorPermissionTestView(APIView):

    permission_classes = [IsEditor]

    def get(self, request):
        return Response(
            {
                "message": "Editor permission granted.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class AuthorPermissionTestView(APIView):

    permission_classes = [IsAuthor]

    def get(self, request):
        return Response(
            {
                "message": "Author permission granted.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class ContributorPermissionTestView(APIView):

    permission_classes = [IsContributor]

    def get(self, request):
        return Response(
            {
                "message": "Contributor permission granted.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class SubscriberPermissionTestView(APIView):

    permission_classes = [IsSubscriber]

    def get(self, request):
        return Response(
            {
                "message": "Subscriber permission granted.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class CreatePostPermissionTestView(APIView):

    permission_classes = [CanCreatePost]

    def get(self, request):
        return Response(
            {
                "message": "You are allowed to create posts.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class PublishPostPermissionTestView(APIView):

    permission_classes = [CanPublishPost]

    def get(self, request):
        return Response(
            {
                "message": "You are allowed to publish posts.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class ReviewPostPermissionTestView(APIView):

    permission_classes = [CanReviewPost]

    def get(self, request):
        return Response(
            {
                "message": "You are allowed to review posts.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class ManageUsersPermissionTestView(APIView):

    permission_classes = [CanManageUsers]

    def get(self, request):
        return Response(
            {
                "message": "You are allowed to manage users.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )




    permission_classes = [CanViewAnalytics]

    def get(self, request):
        return Response(
            {
                "message": "You are allowed to view analytics.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )

class AnalyticsPermissionTestView(APIView):
    """
    Test endpoint for CanViewAnalytics.

    ADMIN and EDITOR are allowed.
    """

    permission_classes = [CanViewAnalytics]

    def get(self, request):
        return Response(
            {
                "message": "You are allowed to view analytics.",
                "role": request.user.role,
                "user": request.user.email,
            },
            status=status.HTTP_200_OK,
        )