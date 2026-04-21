from django.urls import path

from .views import *

DRF_AVAILABLE = True
try:
    from .api_views import (
        ApiOverviewView,
        FeedbackCreateApiView,
        LoginApiView,
        LogoutApiView,
        MyBookingsApiView,
        PackageDetailApiView,
        PackageListApiView,
        RegisterApiView,
    )
except ModuleNotFoundError:
    DRF_AVAILABLE = False


urlpatterns = [
    path('', home, name='home'),
    path('home/', home, name='home'),
    path('help-center/', help_center, name='help_center'),
    path('refund-policy/', refund_policy, name='refund_policy'),
    path('terms-and-conditions/', terms_and_conditions, name='terms_and_conditions'),
    path('feedback/', feedback_page, name='feedback_page'),
    path('feedback/submit/', submit_feedback, name='submit_feedback'),
    path('plan-my-trip/', plan_my_trip, name='plan_my_trip'),
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('admin-portal/login/', admin_login_view, name='admin_login'),
    path('admin-portal/home/', admin_home, name='admin_home'),
    path('packages/', packages, name='packages'),
    path('packages/<int:package_id>/', package_detail, name='package_detail'),
    path('packages/<int:package_id>/book/', book_package, name='book_package'),
    path('packages/<int:package_id>/cancel/', cancel_booking, name='cancel_booking'),
    path('bookings/<int:booking_id>/invoice/', booking_invoice, name='booking_invoice'),
    path('bookings/<int:booking_id>/invoice/download/', download_booking_invoice, name='download_booking_invoice'),
    path('payments/razorpay/callback/', razorpay_callback, name='razorpay_callback'),
    path('payments/razorpay/webhook/', razorpay_webhook, name='razorpay_webhook'),
    path('admin-portal/packages/', manage_packages, name='manage_packages'),
    path('admin-portal/bookings/', manage_bookings, name='manage_bookings'),
    path('admin-portal/feedback/', manage_feedback, name='manage_feedback'),
    path('admin-portal/registrations/', manage_registrations, name='manage_registrations'),
    path('admin-portal/bookings/<int:booking_id>/approval/', update_booking_approval, name='update_booking_approval'),
    path('admin-portal/packages/edit/<int:package_id>/', edit_package, name='edit_package'),
    path('admin-portal/packages/delete/<int:package_id>/', delete_package, name='delete_package'),
    path('admin-portal/feedback/delete/<int:feedback_id>/', delete_feedback, name='delete_feedback'),
    path('packages/manage/', manage_packages, name='manage_packages_legacy'),
    path('packages/manage/edit/<int:package_id>/', edit_package, name='edit_package_legacy'),
    path('packages/manage/delete/<int:package_id>/', delete_package, name='delete_package_legacy'),
    path('logout/', logout_view, name='logout'),

]

if DRF_AVAILABLE:
    urlpatterns += [
        path('api/', ApiOverviewView.as_view(), name='api_overview'),
        path('api/packages/', PackageListApiView.as_view(), name='api_packages'),
        path('api/packages/<int:id>/', PackageDetailApiView.as_view(), name='api_package_detail'),
        path('api/feedback/', FeedbackCreateApiView.as_view(), name='api_feedback_create'),
        path('api/auth/register/', RegisterApiView.as_view(), name='api_register'),
        path('api/auth/login/', LoginApiView.as_view(), name='api_login'),
        path('api/auth/logout/', LogoutApiView.as_view(), name='api_logout'),
        path('api/bookings/me/', MyBookingsApiView.as_view(), name='api_my_bookings'),
    ]
