import re

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import TravelBooking, TravelPackage, UserFeedback, registration


class TravelPackageSerializer(serializers.ModelSerializer):
    display_image_url = serializers.ReadOnlyField()

    class Meta:
        model = TravelPackage
        fields = [
            "id",
            "title",
            "duration",
            "price",
            "display_image_url",
            "short_description",
            "detailed_itinerary",
            "places_included",
            "inclusions",
            "trip_type",
            "payment_details",
            "is_active",
        ]


class UserFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFeedback
        fields = [
            "id",
            "name",
            "email",
            "contact_number",
            "message",
            "rating",
            "satisfaction_score",
            "discovery_source",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class RegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True, min_length=8)
    address = serializers.CharField()
    state = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    pincode = serializers.CharField(max_length=6)

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError("This email is already registered.")
        return normalized

    def validate_password(self, value):
        checks = [
            (r"[A-Z]", "Password must include at least one uppercase letter."),
            (r"[a-z]", "Password must include at least one lowercase letter."),
            (r"\d", "Password must include at least one number."),
            (r"[^A-Za-z0-9]", "Password must include at least one special character."),
        ]
        for pattern, message in checks:
            if not re.search(pattern, value):
                raise serializers.ValidationError(message)

        user = User(username=self.initial_data.get("email", "").strip().lower())
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        user = User.objects.create_user(username=email, email=email, password=password)

        registration.objects.create(
            name=validated_data["name"],
            email=email,
            mobile=validated_data["mobile"],
            password=password,
            address=validated_data["address"],
            state=validated_data["state"],
            city=validated_data["city"],
            pincode=validated_data["pincode"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TravelBookingSerializer(serializers.ModelSerializer):
    package_title = serializers.CharField(source="package.title", read_only=True)

    class Meta:
        model = TravelBooking
        fields = [
            "id",
            "package",
            "package_title",
            "traveler_count",
            "travel_date",
            "contact_number",
            "payment_method",
            "payment_status",
            "approval_status",
            "booked_at",
        ]
        read_only_fields = ["payment_status", "approval_status", "booked_at"]
