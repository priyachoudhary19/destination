from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import models
from django.templatetags.static import static


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


class UserFeedback(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20, default="")
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    satisfaction_score = models.PositiveSmallIntegerField(default=5)
    discovery_source = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.name} - {self.rating} star"


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

    @property
    def display_image_url(self):
        if self.image_url:
            return self.image_url

        image_name = Path(self.image.name).name if self.image else ""
        if image_name:
            static_dir = settings.BASE_DIR / "accounts" / "static" / "images" / "packages"
            candidate_names = [image_name]

            stem = Path(image_name).stem
            suffix = Path(image_name).suffix
            if "_" in stem:
                candidate_names.append(f"{stem.rsplit('_', 1)[0]}{suffix}")

            for candidate_name in candidate_names:
                static_image_path = static_dir / candidate_name
                if static_image_path.exists():
                    return static(f"images/packages/{candidate_name}")

            return self.image.url

        return "https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1200&q=80"

    def save(self, *args, **kwargs):
        old_image_name = None
        if self.pk:
            old_image_name = (
                TravelPackage.objects.filter(pk=self.pk)
                .values_list("image", flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if old_image_name and self.image and old_image_name != self.image.name:
            storage = self.image.storage
            if storage.exists(old_image_name):
                storage.delete(old_image_name)

    def delete(self, *args, **kwargs):
        image_storage = self.image.storage if self.image else None
        image_name = self.image.name if self.image else ""
        super().delete(*args, **kwargs)
        if image_storage and image_name and image_storage.exists(image_name):
            image_storage.delete(image_name)


class TravelBooking(models.Model):
    APPROVAL_STATUS_PENDING = "pending"
    APPROVAL_STATUS_APPROVED = "approved"
    APPROVAL_STATUS_REJECTED = "rejected"
    APPROVAL_STATUS_CHOICES = [
        (APPROVAL_STATUS_PENDING, "Pending Review"),
        (APPROVAL_STATUS_APPROVED, "Approved"),
        (APPROVAL_STATUS_REJECTED, "Rejected"),
    ]

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
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_STATUS_PENDING,
    )
    bus_seats_confirmed = models.BooleanField(default=False)
    train_tickets_confirmed = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True)
    admin_reviewed_at = models.DateTimeField(blank=True, null=True)
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
