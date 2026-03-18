from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.core.mail import send_mail
from django.conf import settings

from .forms import TravelPackageForm
from .models import TravelBooking, TravelPackage, registration


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
    return render(request, "plan_my_trip.html")


@login_required(login_url="/admin-portal/login/")
def admin_home(request):
    if not request.user.is_staff:
        return redirect("admin_login")

    return render(request, "admin_home.html")


def packages(request):
    packages_qs = TravelPackage.objects.filter(is_active=True)

    booked_package_ids = set()
    if request.user.is_authenticated:
        booked_package_ids = set(
            TravelBooking.objects.filter(user=request.user).values_list("package_id", flat=True)
        )

    return render(
        request,
        "packages.html",
        {
            "packages": packages_qs,
            "booked_package_ids": booked_package_ids,
            "is_preview": not request.user.is_authenticated,
        },
    )


@login_required(login_url="/login/")
def book_package(request, package_id):
    if request.method != "POST":
        return redirect("packages")

    package = get_object_or_404(TravelPackage, id=package_id, is_active=True)
    _, created = TravelBooking.objects.get_or_create(user=request.user, package=package)

    if created:
        messages.success(request, f"{package.title} booked successfully.")
    else:
        messages.info(request, f"You already booked {package.title}.")

    return redirect("packages")


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

    return render(request, "admin_bookings.html")


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


def logout_view(request):
    logout(request)
    return redirect("home")
