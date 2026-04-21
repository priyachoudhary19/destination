from django import forms
from django.core.validators import RegexValidator
from django.utils import timezone

from .models import TravelBooking, TravelPackage, UserFeedback


class TravelPackageForm(forms.ModelForm):
    class Meta:
        model = TravelPackage
        fields = [
            "title",
            "duration",
            "price",
            "image_url",
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
        self.fields["image_url"].required = False
        self.fields["image_url"].widget.attrs["placeholder"] = (
            "https://example.com/package-image.jpg"
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("image_url") and instance.image:
            instance.image.delete(save=False)
            instance.image = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class UserFeedbackForm(forms.ModelForm):
    contact_number = forms.CharField(
        validators=[
            RegexValidator(
                regex=r"^[0-9+\-\s]{10,20}$",
                message="Enter a valid contact number.",
            )
        ]
    )
    discovery_source = forms.CharField(required=False)

    class Meta:
        model = UserFeedback
        fields = [
            "name",
            "email",
            "contact_number",
            "message",
            "rating",
            "satisfaction_score",
            "discovery_source",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter your full name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Enter your email address"}),
            "contact_number": forms.TextInput(attrs={"placeholder": "Enter your contact number"}),
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Share your feedback here...",
                }
            ),
            "rating": forms.HiddenInput(),
            "satisfaction_score": forms.HiddenInput(),
            "discovery_source": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["name", "email", "contact_number", "message", "rating"]:
            self.fields[field_name].required = True
        self.fields["satisfaction_score"].required = False
        self.fields["discovery_source"].required = False

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if rating < 1 or rating > 10:
            raise forms.ValidationError("Select a rating between 1 and 10.")
        if rating > 5:
            rating = (rating + 1) // 2
        return rating

    def clean_satisfaction_score(self):
        score = self.cleaned_data.get("satisfaction_score")
        if not score:
            score = self.data.get("rating")
        try:
            score = int(score)
        except (TypeError, ValueError):
            raise forms.ValidationError("Select a satisfaction score between 1 and 10.")
        if score < 1 or score > 10:
            raise forms.ValidationError("Select a satisfaction score between 1 and 10.")
        return score


class TravelBookingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ["traveler_count", "travel_date", "contact_number", "payment_method"]:
            self.fields[field_name].required = True
            self.fields[field_name].widget.attrs["required"] = "required"
        self.fields["payment_method"].choices = [
            (
                TravelBooking.PAYMENT_METHOD_RAZORPAY,
                dict(TravelBooking.PAYMENT_METHOD_CHOICES)[TravelBooking.PAYMENT_METHOD_RAZORPAY],
            ),
            (
                TravelBooking.PAYMENT_METHOD_CASH,
                dict(TravelBooking.PAYMENT_METHOD_CHOICES)[TravelBooking.PAYMENT_METHOD_CASH],
            ),
        ]
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
