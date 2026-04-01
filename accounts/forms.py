from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import TravelBooking, TravelPackage


class TravelPackageForm(forms.ModelForm):
    class Meta:
        model = TravelPackage
        fields = [
            "title",
            "duration",
            "price",
            "image",
            "short_description",
            "detailed_itinerary",
            "places_included",
            "inclusions",
            "trip_type",
            "payment_details",
            "is_active",
            "sort_order",
        ]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "short_description": forms.Textarea(attrs={"rows": 3}),
            "detailed_itinerary": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Day 1: Arrival and local sightseeing\nDay 2: Beach visit and fort tour",
                }
            ),
            "places_included": forms.Textarea(attrs={"rows": 3}),
            "inclusions": forms.Textarea(attrs={"rows": 3}),
            "payment_details": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image

        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        image_name = image.name.lower()
        if not any(image_name.endswith(extension) for extension in allowed_extensions):
            raise ValidationError("Upload JPG, PNG, WEBP, or GIF image.")

        max_size = settings.PACKAGE_IMAGE_MAX_UPLOAD_MB * 1024 * 1024
        if image.size > max_size:
            raise ValidationError(
                f"Image size should be under {settings.PACKAGE_IMAGE_MAX_UPLOAD_MB} MB."
            )

        return image

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("image"):
            instance.image_url = ""
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class TravelBookingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ["traveler_count", "travel_date", "contact_number", "payment_method"]:
            self.fields[field_name].required = True
            self.fields[field_name].widget.attrs["required"] = "required"
        self.fields["travel_date"].widget.attrs["min"] = timezone.localdate().isoformat()

    def clean_travel_date(self):
        travel_date = self.cleaned_data["travel_date"]
        if travel_date < timezone.localdate():
            raise forms.ValidationError("Travel date cannot be earlier than today.")
        return travel_date

    class Meta:
        model = TravelBooking
        fields = [
            "traveler_count",
            "travel_date",
            "contact_number",
            "payment_method",
        ]
        widgets = {
            "traveler_count": forms.NumberInput(
                attrs={"min": 1, "placeholder": "Enter traveler count"}
            ),
            "travel_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "contact_number": forms.TextInput(
                attrs={"placeholder": "Enter contact number"}
            ),
            "payment_method": forms.Select(
                attrs={}
            ),
        }


class BookingApprovalForm(forms.ModelForm):
    class Meta:
        model = TravelBooking
        fields = [
            "bus_seats_confirmed",
            "train_tickets_confirmed",
            "admin_notes",
        ]
        widgets = {
            "admin_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add seat or ticket availability notes for this booking",
                }
            ),
        }
