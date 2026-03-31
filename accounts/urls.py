from django.urls import path

from .views import *


urlpatterns = [
    path('', home, name='home'),
    path('home/', home, name='home'),
    path('plan-my-trip/', plan_my_trip, name='plan_my_trip'),
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('admin-portal/login/', admin_login_view, name='admin_login'),
    path('admin-portal/home/', admin_home, name='admin_home'),
    path('packages/', packages, name='packages'),
    path('packages/<int:package_id>/', package_detail, name='package_detail'),
    path('packages/<int:package_id>/book/', book_package, name='book_package'),
    path('payments/razorpay/callback/', razorpay_callback, name='razorpay_callback'),
    path('payments/razorpay/webhook/', razorpay_webhook, name='razorpay_webhook'),
    path('admin-portal/packages/', manage_packages, name='manage_packages'),
    path('admin-portal/bookings/', manage_bookings, name='manage_bookings'),
    path('admin-portal/bookings/<int:booking_id>/approval/', update_booking_approval, name='update_booking_approval'),
    path('admin-portal/packages/edit/<int:package_id>/', edit_package, name='edit_package'),
    path('admin-portal/packages/delete/<int:package_id>/', delete_package, name='delete_package'),
    path('packages/manage/', manage_packages, name='manage_packages_legacy'),
    path('packages/manage/edit/<int:package_id>/', edit_package, name='edit_package_legacy'),
    path('packages/manage/delete/<int:package_id>/', delete_package, name='delete_package_legacy'),
    path('logout/', logout_view, name='logout'),
]
