from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TravelBooking, TravelPackage


@override_settings(SECURE_SSL_REDIRECT=False)
class PackageBookingFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="traveler@example.com",
            email="traveler@example.com",
            password="pass12345",
        )
        self.admin_user = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )
        self.package = TravelPackage.objects.create(
            title="Goa Escape",
            duration=5,
            price="25000.00",
            short_description="Beach holiday",
            detailed_itinerary="Day 1: Arrival in Goa\nDay 2: Baga Beach and Fort Aguada",
            places_included="Baga Beach, Fort Aguada, Dudhsagar",
            inclusions="Hotel, breakfast, transfers",
            trip_type="Leisure trip",
            payment_details="Pay 30% advance by UPI to confirm the slot.",
        )
        self.package_two = TravelPackage.objects.create(
            title="Manali Adventure",
            duration=8,
            price="42000.00",
            short_description="Mountain break",
            trip_type="Adventure",
        )

    def test_package_detail_preview_requires_login_for_full_trip_details(self):
        response = self.client.get(reverse("package_detail", args=[self.package.id]))

        self.assertContains(response, "Beach holiday")
        self.assertContains(response, "Login to See Full Details")
        self.assertNotContains(response, "Baga Beach, Fort Aguada, Dudhsagar")
        self.assertNotContains(response, "Day 1: Arrival in Goa")

    def test_logged_in_user_sees_admin_added_full_trip_details(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("package_detail", args=[self.package.id]))

        self.assertContains(response, "Baga Beach, Fort Aguada, Dudhsagar")
        self.assertContains(response, "Day 1: Arrival in Goa")
        self.assertContains(response, "Pay 30% advance by UPI to confirm the slot.")

    def test_admin_can_add_package_with_uploaded_image(self):
        self.client.login(username="admin@example.com", password="adminpass123")

        upload = SimpleUploadedFile(
            "kerala-upload-test.jpg",
            b"fake-image-content",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("manage_packages"),
            {
                "title": "Kerala Retreat",
                "duration": 6,
                "price": "31500.00",
                "image": upload,
                "image_url": "",
                "short_description": "Backwater holiday",
                "detailed_itinerary": "Day 1: Arrival",
                "places_included": "Alleppey, Munnar",
                "inclusions": "Hotel, breakfast",
                "trip_type": "Relaxation",
                "payment_details": "Advance required",
                "is_active": "on",
                "sort_order": 3,
            },
        )

        self.assertRedirects(response, reverse("manage_packages"))
        package = TravelPackage.objects.get(title="Kerala Retreat")
        self.assertTrue(package.image.name.startswith("packages/"))
        self.assertEqual(package.image_url, "")
        self.assertIn("/media/packages/", package.display_image_url)
        package.delete()

    def test_logged_in_user_can_create_booking_with_payment_method(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 3,
                "travel_date": "2026-05-10",
                "contact_number": "9876543210",
                "payment_method": TravelBooking.PAYMENT_METHOD_UPI,
                "special_requests": "Need airport pickup",
            },
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        booking = TravelBooking.objects.get(user=self.user, package=self.package)
        self.assertEqual(booking.traveler_count, 3)
        self.assertEqual(booking.payment_status, TravelBooking.PAYMENT_STATUS_PENDING)
        self.assertEqual(booking.payment_method, TravelBooking.PAYMENT_METHOD_UPI)

    def test_booking_requires_all_fields_including_travel_date(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": "",
                "travel_date": "",
                "contact_number": "",
                "payment_method": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.", count=4)
        self.assertFalse(
            TravelBooking.objects.filter(user=self.user, package=self.package).exists()
        )

    def test_booking_rejects_past_travel_date(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 2,
                "travel_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
                "contact_number": "9876543210",
                "payment_method": TravelBooking.PAYMENT_METHOD_UPI,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Travel date cannot be earlier than today.")
        self.assertFalse(
            TravelBooking.objects.filter(user=self.user, package=self.package).exists()
        )

    def test_admin_can_approve_booking_after_confirming_transport(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=10),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.post(
            reverse("update_booking_approval", args=[booking.id]),
            {
                "booking-{}".format(booking.id) + "-admin_notes": "Seats and tickets confirmed by vendor.",
                "action": "approve",
            },
        )

        self.assertRedirects(response, reverse("manage_bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.approval_status, TravelBooking.APPROVAL_STATUS_APPROVED)
        self.assertEqual(booking.admin_notes, "Seats and tickets confirmed by vendor.")
        self.assertIsNotNone(booking.admin_reviewed_at)

    def test_admin_can_reject_booking_with_notes(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=1,
            travel_date=timezone.localdate() + timedelta(days=7),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="25000.00",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.post(
            reverse("update_booking_approval", args=[booking.id]),
            {
                "booking-{}".format(booking.id) + "-admin_notes": "Train tickets are sold out for this date.",
                "action": "reject",
            },
        )

        self.assertRedirects(response, reverse("manage_bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.approval_status, TravelBooking.APPROVAL_STATUS_REJECTED)
        self.assertEqual(booking.admin_notes, "Train tickets are sold out for this date.")
        self.assertIsNotNone(booking.admin_reviewed_at)

    def test_plan_my_trip_filters_by_trip_type_and_budget(self):
        response = self.client.get(
            reverse("plan_my_trip"),
            {
                "trip_type": "Leisure trip",
                "max_budget": "30000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Goa Escape")
        self.assertNotContains(response, "Manali Adventure")

    def test_plan_my_trip_filters_by_search(self):
        response = self.client.get(reverse("plan_my_trip"), {"search": "Manali"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manali Adventure")
        self.assertNotContains(response, "Goa Escape")

    def test_plan_my_trip_shows_only_filters_before_search(self):
        response = self.client.get(reverse("plan_my_trip"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apply filters to view packages")
        self.assertNotContains(response, "Goa Escape")
        self.assertNotContains(response, "Manali Adventure")

    def test_plan_my_trip_shows_meaningful_budget_and_duration_options(self):
        response = self.client.get(reverse("plan_my_trip"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Up to Rs 25,000")
        self.assertContains(response, "Up to Rs 42,000")
        self.assertContains(response, "Up to 5 days")
        self.assertContains(response, "Up to 8 days")
