from rest_framework import serializers

from .models import User


# :::: REGISTRATION
class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True,min_length=8)
    password_confirmation = serializers.CharField(write_only=True)

    class Meta:
        model = User

        fields = [
            "email",
            "username",
            "first_name",
            "last_name",
            "password",
            "password_confirmation",
        ]

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_username(self, value):
        value = value.lower().strip()
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError({"password_confirmation": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirmation")
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user

# :::: LOGIN
class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True
    )

# :::: CHANGE PASSWORD
class ChangePasswordSerializer(serializers.Serializer):

    current_password = serializers.CharField(write_only=True)

    new_password = serializers.CharField(write_only=True,min_length=8)
    new_password_confirmation = serializers.CharField(write_only=True)

    def validate(self, attrs):

        if attrs["new_password"] != attrs["new_password_confirmation"]:
            raise serializers.ValidationError({
                "new_password_confirmation":
                    "Passwords do not match."
            })

        return attrs

# ::: RESET PASSWORD
class ResetPasswordSerializer(serializers.Serializer):

    token = serializers.CharField()

    new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    new_password_confirmation = serializers.CharField(
        write_only=True
    )

    def validate(self, attrs):

        if (
            attrs["new_password"]
            != attrs["new_password_confirmation"]
        ):
            raise serializers.ValidationError({
                "new_password_confirmation":
                    "Passwords do not match."
            })

        return attrs