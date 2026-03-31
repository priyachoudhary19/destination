import base64
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib import error, request as urllib_request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import BookingApprovalForm, TravelBookingForm, TravelPackageForm
from .models import TravelBooking, TravelPackage, registration


logger = logging.getLogger(__name__)


def razorpay_configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def to_paise(amount):
    return int((amount * Decimal("100")).quantize(Decimal("1")))


def create_razorpay_order(booking):
    if not razorpay_configured():
        raise ValueError("Razorpay credentials are missing.")

    payload = {
        "amount": to_paise(booking.payment_amount),
        "currency": booking.currency,
        "receipt": f"booking-{booking.id}",
        "notes": {
            "booking_id": str(booking.id),
            "package_id": str(booking.package_id),
            "user_id": str(booking.user_id),
        },
    }
    request_body = json.dumps(payload).encode("utf-8")
    credentials = f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode("utf-8")
    headers = {
        "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
        "Content-Type": "application/json",
    }
    api_request = urllib_request.Request(
        "https://api.razorpay.com/v1/orders",
        data=request_body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(api_request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        logger.warning("Razorpay order creation failed: %s", body)
        raise ValueError("Razorpay order create nahi ho paaya.") from exc
    except error.URLError as exc:
        logger.warning("Razorpay order creation network error: %s", exc)
        raise ValueError("Razorpay se connection nahi ho paaya.") from exc


def verify_razorpay_signature(order_id, payment_id, signature):
    if not settings.RAZORPAY_KEY_SECRET:
        return False

    payload = f"{order_id}|{payment_id}".encode("utf-8")
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


def verify_razorpay_webhook_signature(body, signature):
    if not settings.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False

    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


def update_booking_payment(booking, payment_id="", signature="", status=None, error_message=""):
    if payment_id:
        booking.razorpay_payment_id = payment_id
    if signature:
        booking.razorpay_signature = signature
    if status:
        booking.payment_status = status
    if error_message:
        booking.last_payment_error = error_message[:255]
    if status in {
        TravelBooking.PAYMENT_STATUS_ADVANCE,
        TravelBooking.PAYMENT_STATUS_COMPLETED,
    }:
        booking.paid_at = timezone.now()
        booking.last_payment_error = ""
    booking.save()


def register(request):
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]


        if User.objects.filter(username=email).exists():
            return render(request, "register.html", {"error": "Email already registered"})

        User.objects.create_user(username=email, email=email, password=password)


        obj = registration()
        obj.name = request.POST["name"]
        obj.email = email
        obj.mobile = request.POST["mobile"]
        obj.password = password
        obj.address = request.POST["address"]
        obj.state = request.POST["state"]
        obj.city = request.POST["city"]
        obj.pincode = request.POST["pincode"]
        obj.save()

        # 📧 Send Email
        send_mail(
            'Registration Successful - Dreamland Destinations',
            'Hello! Your registration for Dreamland Destinations was successful.',
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )

        messages.success(request, "Registration successful. Please login.")
        return redirect("login")

    return render(request, "register.html")


def login_view(request):
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user:
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect("home")

        return render(request, "login.html", {"error": "Invalid credentials", "next": next_url})

    return render(request, "login.html", {"next": next_url})


def admin_login_view(request):
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin_home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect("admin_home")

        return render(
            request,
            "admin_login.html",
            {"error": "Invalid admin credentials", "next": next_url},
        )

    return render(request, "admin_login.html", {"next": next_url})


def home(request):
    return render(request, "home.html")


def plan_my_trip(request):
    active_packages_qs = TravelPackage.objects.filter(is_active=True)
    packages_qs = active_packages_qs

    search = request.GET.get("search", "").strip()
    trip_type = request.GET.get("trip_type", "").strip()
    max_budget = request.GET.get("max_budget", "").strip()
    max_duration = request.GET.get("max_duration", "").strip()

    active_filters = [value for value in [search, trip_type, max_budget, max_duration] if value]
    has_active_filters = bool(active_filters)

    if has_active_filters:
        if search:
            packages_qs = packages_qs.filter(title__icontains=search)

        if trip_type:
            packages_qs = packages_qs.filter(trip_type__iexact=trip_type)

        if max_budget.isdigit():
            packages_qs = packages_qs.filter(price__lte=max_budget)

        if max_duration.isdigit():
            packages_qs = packages_qs.filter(duration__lte=max_duration)
    else:
        packages_qs = TravelPackage.objects.none()

    booked_package_ids = set()
    if request.user.is_authenticated:
        booked_package_ids = set(
            TravelBooking.objects.filter(user=request.user).values_list("package_id", flat=True)
        )

    trip_types = [
        item
        for item in active_packages_qs
        .exclude(trip_type="")
        .values_list("trip_type", flat=True)
        .distinct()
        .order_by("trip_type")
    ]
    budget_options = [
        {
            "value": str(int(price)),
            "label": f"Rs {int(price):,}",
        }
        for price in active_packages_qs.values_list("price", flat=True).distinct().order_by("price")
    ]
    duration_options = list(
        active_packages_qs.values_list("duration", flat=True).distinct().order_by("duration")
    )

    return render(
        request,
        "plan_my_trip.html",
        {
            "packages": packages_qs,
            "booked_package_ids": booked_package_ids,
            "trip_types": trip_types,
            "budget_options": budget_options,
            "duration_options": duration_options,
            "selected_search": search,
            "selected_trip_type": trip_type,
            "selected_max_budget": max_budget,
            "selected_max_duration": max_duration,
            "active_filter_count": len(active_filters),
            "has_active_filters": has_active_filters,
        },
    )


@login_required(login_url="/admin-portal/login/")
def admin_home(request):
    if not request.user.is_staff:
        return redirect("admin_login")

    return render(request, "admin_home.html")


def packages(request):
    packages_qs = TravelPackage.objects.filter(is_active=True)

    booked_package_ids = set()
    user_bookings = {}
    if request.user.is_authenticated:
        bookings = TravelBooking.objects.filter(user=request.user).select_related("package")
        booked_package_ids = {booking.package_id for booking in bookings}
        user_bookings = {booking.package_id: booking for booking in bookings}

    return render(
        request,
        "packages.html",
        {
            "packages": packages_qs,
            "booked_package_ids": booked_package_ids,
            "user_bookings": user_bookings,
            "is_preview": not request.user.is_authenticated,
        },
    )


def package_detail(request, package_id):
    package = get_object_or_404(TravelPackage, id=package_id, is_active=True)
    booking = None
    booking_form = None
    payment_context = None
    normalized_trip_type = package.trip_type.replace("\r", "/").replace("\n", "/")
    trip_type_segments = [
        segment.strip() for segment in normalized_trip_type.split("/") if segment.strip()
    ] or ["Comfort + sightseeing"]

    if request.user.is_authenticated:
        booking = TravelBooking.objects.filter(user=request.user, package=package).first()
        booking_form = TravelBookingForm(instance=booking)
        if (
            booking
            and booking.payment_method == TravelBooking.PAYMENT_METHOD_RAZORPAY
            and booking.payment_status != TravelBooking.PAYMENT_STATUS_COMPLETED
            and booking.razorpay_order_id
            and razorpay_configured()
        ):
            payment_context = {
                "key_id": settings.RAZORPAY_KEY_ID,
                "amount": to_paise(booking.payment_amount),
                "currency": booking.currency,
                "company_name": settings.RAZORPAY_COMPANY_NAME,
                "description": f"{package.title} booking",
                "order_id": booking.razorpay_order_id,
                "callback_url": request.build_absolute_uri(reverse("razorpay_callback")),
                "prefill_name": request.user.get_full_name() or request.user.username,
                "prefill_email": request.user.email,
                "prefill_contact": booking.contact_number,
                "theme_color": "#1f6feb",
                "auto_open": request.GET.get("pay") == "1",
            }

    return render(
        request,
        "package_detail.html",
        {
            "package": package,
            "booking": booking,
            "booking_form": booking_form,
            "payment_context": payment_context,
            "trip_type_segments": trip_type_segments,
            "razorpay_ready": razorpay_configured(),
            "is_preview": not request.user.is_authenticated,
        },
    )


@login_required(login_url="/login/")
def book_package(request, package_id):


    package = get_object_or_404(TravelPackage, id=package_id, is_active=True)
    if request.method != "POST":
        return redirect("package_detail", package_id=package.id)

    existing_booking = TravelBooking.objects.filter(user=request.user, package=package).first()
    form = TravelBookingForm(request.POST, instance=existing_booking)

    if not form.is_valid():
        return render(
            request,
            "package_detail.html",
            {
                "package": package,
                "booking": existing_booking,
                "booking_form": form,
                "is_preview": False,
            },
        )

    booking = form.save(commit=False)
    booking.user = request.user
    booking.package = package
    created = booking.pk is None
    booking.payment_amount = booking.total_price()
    booking.currency = settings.RAZORPAY_CURRENCY or "INR"

    if booking.payment_method != TravelBooking.PAYMENT_METHOD_RAZORPAY:
        booking.razorpay_order_id = ""
        booking.razorpay_payment_id = ""
        booking.razorpay_signature = ""
        booking.razorpay_last_event_id = ""
        booking.last_payment_error = ""

    booking.save()

    if booking.payment_method == TravelBooking.PAYMENT_METHOD_RAZORPAY:
        if booking.payment_status == TravelBooking.PAYMENT_STATUS_COMPLETED:
            messages.info(request, "Is booking ka payment already complete hai.")
            return redirect("package_detail", package_id=package.id)

        try:
            order_data = create_razorpay_order(booking)
        except ValueError as exc:
            booking.last_payment_error = str(exc)
            booking.save(update_fields=["last_payment_error"])
            messages.error(request, str(exc))
            return redirect("package_detail", package_id=package.id)

        booking.razorpay_order_id = order_data.get("id", "")
        booking.last_payment_error = ""
        booking.payment_status = TravelBooking.PAYMENT_STATUS_PENDING
        booking.save(update_fields=["razorpay_order_id", "last_payment_error", "payment_status"])

        if created:
            messages.success(request, f"{package.title} booking created. Ab payment complete kar dijiye.")
        else:
            messages.info(request, f"{package.title} booking update ho gayi. Payment complete kar dijiye.")
        return redirect(f"{reverse('package_detail', args=[package.id])}?pay=1")

    if created:
        messages.success(request, f"{package.title} booked successfully.")
    else:
        messages.info(request, f"Your booking details for {package.title} have been updated.")

    return redirect("package_detail", package_id=package.id)


@login_required(login_url="/admin-portal/login/")
def manage_packages(request):
    if not request.user.is_staff:
        messages.error(request, "Only admin users can access package management.")
        return redirect("admin_login")

    if request.method == "POST":
        form = TravelPackageForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Package added successfully.")
            return redirect("manage_packages")
    else:
        form = TravelPackageForm()

    package_list = TravelPackage.objects.all()
    return render(
        request,
        "admin_packages.html",
        {
            "form": form,
            "package_list": package_list,
        },
    )


@login_required(login_url="/admin-portal/login/")
def manage_bookings(request):
    if not request.user.is_staff:
        return redirect("admin_login")

    return render(request, "admin_bookings.html", {"bookings": _booking_rows_with_forms()})


@login_required(login_url="/admin-portal/login/")
def update_booking_approval(request, booking_id):
    if not request.user.is_staff:
        return redirect("admin_login")

    if request.method != "POST":
        return redirect("manage_bookings")

    booking = get_object_or_404(TravelBooking, id=booking_id)
    action = request.POST.get("action")
    form = BookingApprovalForm(request.POST, instance=booking, prefix=f"booking-{booking.id}")

    if not form.is_valid():
        messages.error(request, "Please correct the booking review details and try again.")
        return render(request, "admin_bookings.html", {"bookings": _booking_rows_with_forms()})

    booking = form.save(commit=False)
    booking.admin_reviewed_at = timezone.now()
    if action == "approve":
        booking.approval_status = TravelBooking.APPROVAL_STATUS_APPROVED
        messages.success(request, f"Booking for {booking.package.title} approved.")
    elif action == "reject":
        booking.approval_status = TravelBooking.APPROVAL_STATUS_REJECTED
        messages.success(request, f"Booking for {booking.package.title} rejected.")
    else:
        messages.error(request, "Unknown booking action.")
        return redirect("manage_bookings")

    booking.save()
    return redirect("manage_bookings")


def _booking_rows_with_forms():
    bookings = TravelBooking.objects.select_related("user", "package").all()
    booking_users = [booking.user for booking in bookings]
    registration_map = {
        item.email: item.name
        for item in registration.objects.filter(
            email__in=[user.email for user in booking_users if user.email]
        )
    }

    for booking in bookings:
        email = booking.user.email or "-"
        booking.display_email = email
        booking.display_name = (
            registration_map.get(booking.user.email)
            or booking.user.get_full_name()
            or booking.user.username
        )
        booking.display_amount = booking.payment_amount or booking.total_price()
        booking.approval_form = BookingApprovalForm(instance=booking, prefix=f"booking-{booking.id}")

    return bookings


@login_required(login_url="/admin-portal/login/")
def delete_package(request, package_id):
    if not request.user.is_staff:
        return redirect("admin_login")

    if request.method == "POST":
        package = get_object_or_404(TravelPackage, id=package_id)
        package.delete()
        messages.success(request, "Package deleted.")

    return redirect("manage_packages")


@login_required(login_url="/admin-portal/login/")
def edit_package(request, package_id):
    if not request.user.is_staff:
        return redirect("admin_login")

    package = get_object_or_404(TravelPackage, id=package_id)

    if request.method == "POST":
        form = TravelPackageForm(request.POST, request.FILES, instance=package)
        if form.is_valid():
            form.save()
            messages.success(request, "Package updated successfully.")
            return redirect("manage_packages")
    else:
        form = TravelPackageForm(instance=package)

    return render(request, "admin_package_edit.html", {"form": form, "package": package})


@csrf_exempt
def razorpay_callback(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    order_id = request.POST.get("razorpay_order_id", "").strip()
    payment_id = request.POST.get("razorpay_payment_id", "").strip()
    signature = request.POST.get("razorpay_signature", "").strip()

    if not order_id or not payment_id or not signature:
        return HttpResponseBadRequest("Missing payment details.")

    booking = TravelBooking.objects.filter(razorpay_order_id=order_id).select_related("package").first()
    if not booking:
        return HttpResponseBadRequest("Booking not found.")

    if not verify_razorpay_signature(order_id, payment_id, signature):
        update_booking_payment(
            booking,
            payment_id=payment_id,
            signature=signature,
            status=TravelBooking.PAYMENT_STATUS_FAILED,
            error_message="Payment signature verification failed.",
        )
        return HttpResponseForbidden("Signature verification failed.")

    update_booking_payment(
        booking,
        payment_id=payment_id,
        signature=signature,
        status=TravelBooking.PAYMENT_STATUS_COMPLETED,
    )
    messages.success(request, f"Payment successful for {booking.package.title}.")
    return redirect("package_detail", package_id=booking.package_id)


@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    signature = request.headers.get("X-Razorpay-Signature", "")
    body = request.body
    if not verify_razorpay_webhook_signature(body, signature):
        return HttpResponseForbidden("Webhook signature verification failed.")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    event = payload.get("event", "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})
    order_id = payment_entity.get("order_id") or order_entity.get("id")

    if not order_id:
        return HttpResponse("ok")

    booking = TravelBooking.objects.filter(razorpay_order_id=order_id).first()
    if not booking:
        return HttpResponse("ok")

    if event_id and booking.razorpay_last_event_id == event_id:
        return HttpResponse("ok")

    booking.razorpay_last_event_id = event_id

    if event in {"payment.captured", "order.paid"}:
        booking.payment_status = TravelBooking.PAYMENT_STATUS_COMPLETED
        booking.razorpay_payment_id = payment_entity.get("id", booking.razorpay_payment_id)
        booking.paid_at = timezone.now()
        booking.last_payment_error = ""
    elif event == "payment.authorized":
        booking.payment_status = TravelBooking.PAYMENT_STATUS_ADVANCE
        booking.razorpay_payment_id = payment_entity.get("id", booking.razorpay_payment_id)
        booking.paid_at = booking.paid_at or timezone.now()
        booking.last_payment_error = ""
    elif event == "payment.failed":
        booking.payment_status = TravelBooking.PAYMENT_STATUS_FAILED
        booking.razorpay_payment_id = payment_entity.get("id", booking.razorpay_payment_id)
        error_description = payment_entity.get("error_description") or "Payment failed."
        booking.last_payment_error = error_description[:255]

    booking.save()
    return HttpResponse("ok")


def logout_view(request):
    logout(request)
    return redirect("home")
