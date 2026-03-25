from django.db import models
from decimal import Decimal


class Author(models.Model):
    name = models.CharField(max_length=100)
    tagline = models.TextField()


class registration(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=10)
    password = models.CharField(max_length=100)
    address = models.TextField()
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6)

    def __str__(self):
        return self.name


class TravelPackage(models.Model):
    title = models.CharField(max_length=120)
    duration = models.PositiveIntegerField(help_text="Duration in days")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.FileField(upload_to="packages/", blank=True, null=True)
    image_url = models.URLField(blank=True)
    short_description = models.CharField(max_length=220, blank=True)
    detailed_itinerary = models.TextField(blank=True)
    places_included = models.TextField(blank=True)
    inclusions = models.TextField(blank=True)
    trip_type = models.CharField(max_length=120, blank=True)
    payment_details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class TravelBooking(models.Model):
    PAYMENT_STATUS_PENDING = "pending"
    PAYMENT_STATUS_ADVANCE = "advance_paid"
    PAYMENT_STATUS_COMPLETED = "completed"
    PAYMENT_STATUS_FAILED = "failed"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, "Pending"),
        (PAYMENT_STATUS_ADVANCE, "Advance Paid"),
        (PAYMENT_STATUS_COMPLETED, "Completed"),
        (PAYMENT_STATUS_FAILED, "Failed"),
    ]

    PAYMENT_METHOD_RAZORPAY = "razorpay"
    PAYMENT_METHOD_UPI = "upi"
    PAYMENT_METHOD_BANK = "bank_transfer"
    PAYMENT_METHOD_CASH = "cash"
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_RAZORPAY, "Razorpay (Online Payment)"),
        (PAYMENT_METHOD_UPI, "UPI"),
        (PAYMENT_METHOD_BANK, "Bank Transfer"),
        (PAYMENT_METHOD_CASH, "Cash at Office"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    package = models.ForeignKey(TravelPackage, on_delete=models.CASCADE)
    traveler_count = models.PositiveIntegerField(default=1)
    travel_date = models.DateField(blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True)
    special_requests = models.TextField(blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_UPI,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING,
    )
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="INR")
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    razorpay_last_event_id = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    last_payment_error = models.CharField(max_length=255, blank=True)
    booked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "package")
        ordering = ["-booked_at"]

    def __str__(self):
        return f"{self.user.username} - {self.package.title}"

    def total_price(self):
        return self.package.price * self.traveler_count
