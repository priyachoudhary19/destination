from datetime import timedelta
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import TravelBookingForm
from .models import TravelBooking, TravelPackage, UserFeedback, registration


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
        registration.objects.create(
            name="Priya Sharma",
            email="traveler@example.com",
            mobile="9876543210",
            password="pass12345",
            address="Beach Road",
            state="Goa",
            city="Panaji",
            pincode="403001",
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

    def test_login_page_sets_csrf_cookie(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_register_page_sets_csrf_cookie(self):
        response = self.client.get(reverse("register"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_logged_in_user_sees_admin_added_full_trip_details(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("package_detail", args=[self.package.id]))

        self.assertContains(response, "Baga Beach, Fort Aguada, Dudhsagar")
        self.assertContains(response, "Day 1: Arrival in Goa")
        self.assertContains(response, "Pay 30% advance by UPI to confirm the slot.")

    def test_admin_can_add_package_with_image_url(self):
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.post(
            reverse("manage_packages"),
            {
                "title": "Kerala Retreat",
                "duration": 6,
                "price": "31500.00",
                "image_url": "https://example.com/kerala.jpg",
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
        self.assertEqual(package.image_url, "https://example.com/kerala.jpg")
        self.assertEqual(package.display_image_url, "https://example.com/kerala.jpg")

    def test_logged_in_user_can_create_booking_with_payment_method(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 3,
                "travel_date": "2026-05-10",
                "contact_number": "9876543210",
                "payment_method": TravelBooking.PAYMENT_METHOD_CASH,
                "special_requests": "Need airport pickup",
            },
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        booking = TravelBooking.objects.get(user=self.user, package=self.package)
        self.assertEqual(booking.traveler_count, 3)
        self.assertEqual(booking.payment_status, TravelBooking.PAYMENT_STATUS_PENDING)
        self.assertEqual(booking.payment_method, TravelBooking.PAYMENT_METHOD_CASH)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Booking Confirmed - Goa Escape", mail.outbox[0].subject)
        self.assertIn("traveler@example.com", mail.outbox[0].to)
        self.assertIn("Hello Priya Sharma,", mail.outbox[0].body)
        self.assertIn("Travelers: 3", mail.outbox[0].body)

    def test_booking_email_never_uses_email_address_as_greeting_name(self):
        registration.objects.filter(email="traveler@example.com").delete()
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 2,
                "travel_date": "2026-05-11",
                "contact_number": "9876543210",
                "payment_method": TravelBooking.PAYMENT_METHOD_CASH,
            },
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Hello Traveler,", mail.outbox[0].body)
        self.assertNotIn("Hello traveler@example.com,", mail.outbox[0].body)

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

    def test_booking_form_limits_payment_methods_to_razorpay_and_cash(self):
        form = TravelBookingForm()

        self.assertEqual(
            list(form.fields["payment_method"].choices),
            [
                (
                    TravelBooking.PAYMENT_METHOD_RAZORPAY,
                    "Razorpay (Online Payment)",
                ),
                (
                    TravelBooking.PAYMENT_METHOD_CASH,
                    "Cash at Office",
                ),
            ],
        )

    def test_booking_rejects_past_travel_date(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 2,
                "travel_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
                "contact_number": "9876543210",
                "payment_method": TravelBooking.PAYMENT_METHOD_CASH,
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

    def test_user_can_cancel_unpaid_booking(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=5),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("cancel_booking", args=[self.package.id]),
            {"cancellation_reason": "My travel dates have changed."},
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        booking.refresh_from_db()
        self.assertEqual(booking.approval_status, TravelBooking.APPROVAL_STATUS_CANCELLED)
        self.assertEqual(booking.cancellation_reason, "My travel dates have changed.")
        self.assertIsNotNone(booking.admin_reviewed_at)

    def test_user_must_provide_reason_to_cancel_booking(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=5),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("cancel_booking", args=[self.package.id]),
            {"cancellation_reason": "   "},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please share a reason before cancelling your booking.")
        booking.refresh_from_db()
        self.assertNotEqual(booking.approval_status, TravelBooking.APPROVAL_STATUS_CANCELLED)

    def test_user_cannot_cancel_paid_booking_from_self_service(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=5),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_RAZORPAY,
            payment_status=TravelBooking.PAYMENT_STATUS_COMPLETED,
            payment_amount="50000.00",
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("cancel_booking", args=[self.package.id]),
            {"cancellation_reason": "I no longer need this trip."},
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        booking.refresh_from_db()
        self.assertNotEqual(booking.approval_status, TravelBooking.APPROVAL_STATUS_CANCELLED)
        self.assertEqual(booking.payment_status, TravelBooking.PAYMENT_STATUS_COMPLETED)

    def test_cancelled_booking_can_be_rebooked(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=1,
            travel_date=timezone.localdate() + timedelta(days=5),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="25000.00",
            approval_status=TravelBooking.APPROVAL_STATUS_CANCELLED,
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 4,
                "travel_date": "2026-05-15",
                "contact_number": "9999999999",
                "payment_method": TravelBooking.PAYMENT_METHOD_CASH,
            },
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        booking.refresh_from_db()
        self.assertEqual(booking.approval_status, TravelBooking.APPROVAL_STATUS_PENDING)
        self.assertEqual(booking.traveler_count, 4)
        self.assertEqual(booking.contact_number, "9999999999")
        self.assertEqual(booking.cancellation_reason, "")

    def test_user_can_view_booking_invoice(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=9),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("booking_invoice", args=[booking.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BOOKING INVOICE")
        self.assertContains(response, "Goa Escape")
        self.assertContains(response, "Priya Sharma")

    def test_user_can_download_booking_invoice(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=9),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("download_booking_invoice", args=[booking.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("Invoice Number", response.content.decode("utf-8"))

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_123",
        RAZORPAY_KEY_SECRET="secret_123",
        RAZORPAY_CURRENCY="INR",
    )
    @patch("accounts.views.urllib_request.urlopen")
    def test_razorpay_booking_creates_order_and_redirects_to_checkout(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"id": "order_test_123"}).encode("utf-8")
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_context
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("book_package", args=[self.package.id]),
            {
                "traveler_count": 2,
                "travel_date": "2026-05-20",
                "contact_number": "9876543210",
                "payment_method": TravelBooking.PAYMENT_METHOD_RAZORPAY,
            },
        )

        self.assertRedirects(response, f"{reverse('package_detail', args=[self.package.id])}?pay=1")
        booking = TravelBooking.objects.get(user=self.user, package=self.package)
        self.assertEqual(booking.razorpay_order_id, "order_test_123")
        self.assertEqual(booking.payment_status, TravelBooking.PAYMENT_STATUS_PENDING)
        self.assertEqual(booking.payment_method, TravelBooking.PAYMENT_METHOD_RAZORPAY)

    @override_settings(RAZORPAY_KEY_SECRET="secret_123")
    def test_razorpay_callback_marks_booking_as_paid(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=9),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_RAZORPAY,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
            razorpay_order_id="order_test_123",
        )
        signature = hmac.new(
            b"secret_123",
            b"order_test_123|pay_test_123",
            hashlib.sha256,
        ).hexdigest()

        response = self.client.post(
            reverse("razorpay_callback"),
            {
                "razorpay_order_id": "order_test_123",
                "razorpay_payment_id": "pay_test_123",
                "razorpay_signature": signature,
            },
        )

        self.assertRedirects(response, reverse("package_detail", args=[self.package.id]))
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, TravelBooking.PAYMENT_STATUS_COMPLETED)
        self.assertEqual(booking.razorpay_payment_id, "pay_test_123")

    @override_settings(RAZORPAY_WEBHOOK_SECRET="webhook_secret_123")
    def test_razorpay_webhook_marks_booking_as_paid(self):
        booking = TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=9),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_RAZORPAY,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
            razorpay_order_id="order_test_456",
        )
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_456",
                        "order_id": "order_test_456",
                    }
                }
            },
        }
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"webhook_secret_123", body, hashlib.sha256).hexdigest()

        response = self.client.post(
            reverse("razorpay_webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
            HTTP_X_RAZORPAY_EVENT_ID="evt_test_456",
        )

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, TravelBooking.PAYMENT_STATUS_COMPLETED)
        self.assertEqual(booking.razorpay_payment_id, "pay_test_456")

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

    def test_cancelled_booking_does_not_show_as_active_booking_in_listings(self):
        TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=1,
            travel_date=timezone.localdate() + timedelta(days=6),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="25000.00",
            approval_status=TravelBooking.APPROVAL_STATUS_CANCELLED,
        )
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("packages"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "View Booking & Payment")

    def test_admin_can_see_user_cancellation_reason(self):
        TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=1,
            travel_date=timezone.localdate() + timedelta(days=6),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="25000.00",
            approval_status=TravelBooking.APPROVAL_STATUS_CANCELLED,
            cancellation_reason="A family event came up unexpectedly.",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancellation reason:")
        self.assertContains(response, "A family event came up unexpectedly.")

    def test_admin_manage_bookings_shows_payment_status(self):
        TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=10),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_RAZORPAY,
            payment_status=TravelBooking.PAYMENT_STATUS_COMPLETED,
            payment_amount="50000.00",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Status")
        self.assertContains(response, "Completed")

    def test_admin_manage_bookings_shows_contact_column_without_approval_column(self):
        TravelBooking.objects.create(
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

        response = self.client.get(reverse("manage_bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<th>Contact</th>", html=True)
        self.assertContains(response, 'class="booking-contact-cell"', html=False)
        self.assertContains(response, 'class="booking-col-contact"', html=False)
        self.assertNotContains(response, "<th>Approval</th>", html=True)
        self.assertNotContains(response, 'class="booking-approval-cell"', html=False)
        self.assertNotContains(response, 'class="booking-col-approval"', html=False)
        self.assertContains(response, "9876543210")

    def test_admin_manage_bookings_shows_reviewed_state_in_action_column(self):
        TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=10),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
            approval_status=TravelBooking.APPROVAL_STATUS_APPROVED,
        )
        TravelBooking.objects.create(
            user=self.admin_user,
            package=self.package_two,
            traveler_count=1,
            travel_date=timezone.localdate() + timedelta(days=12),
            contact_number="9999999999",
            payment_method=TravelBooking.PAYMENT_METHOD_CASH,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="42000.00",
            approval_status=TravelBooking.APPROVAL_STATUS_REJECTED,
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reviewed")
        self.assertContains(response, "Approved")
        self.assertContains(response, "Rejected")

    def test_admin_manage_bookings_uses_abbreviated_month_date_format(self):
        TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.datetime(2026, 9, 1).date(),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_UPI,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "01 Sep 2026")
        self.assertNotContains(response, "01/09/2026")

    def test_admin_manage_bookings_treats_stale_paid_booking_as_completed(self):
        TravelBooking.objects.create(
            user=self.user,
            package=self.package,
            traveler_count=2,
            travel_date=timezone.localdate() + timedelta(days=10),
            contact_number="9876543210",
            payment_method=TravelBooking.PAYMENT_METHOD_RAZORPAY,
            payment_status=TravelBooking.PAYMENT_STATUS_PENDING,
            payment_amount="50000.00",
            razorpay_payment_id="pay_stale_123",
            paid_at=timezone.now(),
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed")
        self.assertNotContains(response, '<strong class="booking-status-pill booking-payment-pending">Pending</strong>', html=True)

    def test_plan_my_trip_shows_meaningful_budget_and_duration_options(self):
        response = self.client.get(reverse("plan_my_trip"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Up to Rs 25,000")
        self.assertContains(response, "Up to Rs 42,000")
        self.assertContains(response, "Up to 5 days")
        self.assertContains(response, "Up to 8 days")

    def test_home_does_not_show_question_or_feedback_options(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Ask Questions")
        self.assertNotContains(response, "Provide Feedback")

    def test_feedback_submission_endpoint_saves_feedback(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("submit_feedback"),
            {
                "name": "Priya Sharma",
                "email": "priya@example.com",
                "contact_number": "9876543210",
                "message": "Loved the itinerary and support quality.",
                "rating": 9,
                "discovery_source": "Google search",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        feedback = UserFeedback.objects.latest("id")
        self.assertEqual(feedback.satisfaction_score, 9)
        self.assertEqual(feedback.discovery_source, "Google search")

    def test_feedback_submission_requires_valid_fields(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("submit_feedback"),
            {
                "name": "",
                "email": "invalid-email",
                "contact_number": "abc",
                "message": "",
                "rating": 0,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["ok"], False)
        self.assertIn("email", payload["errors"])
        self.assertIn("rating", payload["errors"])

    def test_feedback_submission_requires_logged_in_user(self):
        response = self.client.post(
            reverse("submit_feedback"),
            {
                "name": "Guest",
                "email": "guest@example.com",
                "contact_number": "9876543210",
                "message": "Nice trip.",
                "rating": 4,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["ok"], False)

    def test_feedback_submission_redirects_on_regular_post(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("submit_feedback"),
            {
                "name": "Priya Sharma",
                "email": "priya@example.com",
                "contact_number": "9876543210",
                "message": "Loved the itinerary and support quality.",
                "rating": 8,
                "discovery_source": "Social media",
            },
        )

        self.assertRedirects(response, reverse("home"))

    def test_feedback_page_submission_redirects_to_home(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.post(
            reverse("submit_feedback"),
            {
                "name": "Priya Sharma",
                "email": "priya@example.com",
                "contact_number": "9876543210",
                "message": "Loved the itinerary and support quality.",
                "rating": 8,
                "discovery_source": "Social media",
                "return_to": "home",
            },
        )

        self.assertRedirects(response, reverse("home"))

    def test_home_hides_feedback_button_for_logged_out_visitors(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Rate your experience")

    def test_home_does_not_show_feedback_button_for_logged_in_user(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Rate your experience")
        self.assertNotContains(response, "Give Feedback")
        self.assertNotContains(response, '<a class="nav-link" href="%s">Feedback</a>' % reverse("feedback_page"), html=True)

    def test_home_shows_logged_in_user_name_in_greeting(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WELCOME BACK")
        self.assertContains(response, "Hello, Priya Sharma")

    def test_feedback_page_requires_login(self):
        response = self.client.get(reverse("feedback_page"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_feedback_page_renders_for_logged_in_user(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("feedback_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback Time!")
        self.assertContains(response, "How satisfied were you when using the website?")
        self.assertContains(response, "Send")

    def test_footer_shows_feedback_link_for_logged_in_user(self):
        self.client.login(username="traveler@example.com", password="pass12345")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("feedback_page"))

    def test_admin_feedback_management_lists_entries(self):
        from .models import UserFeedback

        UserFeedback.objects.create(
            name="Riya",
            email="riya@example.com",
            contact_number="9999999999",
            message="Great planning support.",
            rating=4,
            satisfaction_score=8,
            discovery_source="Google search",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_feedback"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback Management")
        self.assertContains(response, "riya@example.com")
        self.assertContains(response, "8/10")
        self.assertContains(response, "Google search")

    def test_admin_home_hides_registration_management_card(self):
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("admin_home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "User Registrations")
        self.assertNotContains(response, "Total registered:")
        self.assertNotContains(response, reverse("manage_registrations"))

    def test_admin_registration_management_lists_total_and_details(self):
        registration.objects.create(
            name="Aman Verma",
            email="aman@example.com",
            mobile="9998887776",
            password="Aman@123",
            address="MG Road",
            state="Delhi",
            city="New Delhi",
            pincode="110001",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.get(reverse("manage_registrations"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registered Users")
        self.assertContains(response, "Total Registrations")
        self.assertContains(response, "2")
        self.assertContains(response, "Priya Sharma")
        self.assertContains(response, "traveler@example.com")
        self.assertContains(response, "9876543210")
        self.assertContains(response, "City:")
        self.assertContains(response, "Panaji")
        self.assertContains(response, "State:")
        self.assertContains(response, "Goa")
        self.assertContains(response, "PIN: 403001")
        self.assertContains(response, "Aman Verma")
        self.assertContains(response, "aman@example.com")
        self.assertContains(response, "MG Road")

    def test_admin_can_delete_feedback_entry(self):
        from .models import UserFeedback

        feedback = UserFeedback.objects.create(
            name="Riya",
            email="riya@example.com",
            contact_number="9999999999",
            message="Great planning support.",
            rating=4,
            satisfaction_score=8,
            discovery_source="Friends",
        )
        self.client.login(username="admin@example.com", password="adminpass123")

        response = self.client.post(reverse("delete_feedback", args=[feedback.id]))

        self.assertRedirects(response, reverse("manage_feedback"))
        self.assertFalse(UserFeedback.objects.filter(id=feedback.id).exists())
