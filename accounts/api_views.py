from django.contrib.auth import authenticate, login, logout
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TravelBooking, TravelPackage
from .serializers import (
    LoginSerializer,
    RegistrationSerializer,
    TravelBookingSerializer,
    TravelPackageSerializer,
    UserFeedbackSerializer,
)


class ApiOverviewView(APIView):
    """
    Lightweight route index so developers can quickly discover available DRF endpoints.
    """

    def get(self, request):
        return Response(
            {
                "message": "Dreamland API is running.",
                "endpoints": {
                    "packages_list": "/api/packages/",
                    "package_detail": "/api/packages/<id>/",
                    "feedback_submit": "/api/feedback/",
                    "auth_register": "/api/auth/register/",
                    "auth_login": "/api/auth/login/",
                    "auth_logout": "/api/auth/logout/",
                    "my_bookings": "/api/bookings/me/",
                },
            }
        )


class PackageListApiView(generics.ListAPIView):
    serializer_class = TravelPackageSerializer

    def get_queryset(self):
        queryset = TravelPackage.objects.filter(is_active=True)
        search = self.request.query_params.get("search", "").strip()
        trip_type = self.request.query_params.get("trip_type", "").strip()
        max_budget = self.request.query_params.get("max_budget", "").strip()
        max_duration = self.request.query_params.get("max_duration", "").strip()

        if search:
            queryset = queryset.filter(title__icontains=search)
        if trip_type:
            queryset = queryset.filter(trip_type__iexact=trip_type)
        if max_budget.isdigit():
            queryset = queryset.filter(price__lte=max_budget)
        if max_duration.isdigit():
            queryset = queryset.filter(duration__lte=max_duration)
        return queryset


class PackageDetailApiView(generics.RetrieveAPIView):
    serializer_class = TravelPackageSerializer
    queryset = TravelPackage.objects.filter(is_active=True)
    lookup_field = "id"


class FeedbackCreateApiView(generics.CreateAPIView):
    serializer_class = UserFeedbackSerializer


class RegisterApiView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "ok": True,
                "message": "Registration successful.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginApiView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        user = authenticate(request, username=email, password=password)
        if not user:
            return Response(
                {"ok": False, "message": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(
            {
                "ok": True,
                "message": "Login successful.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                },
            }
        )


class LogoutApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"ok": True, "message": "Logout successful."})


class MyBookingsApiView(generics.ListAPIView):
    serializer_class = TravelBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TravelBooking.objects.filter(user=self.request.user).select_related("package")
