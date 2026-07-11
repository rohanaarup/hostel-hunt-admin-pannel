"""otp_auth/urls.py"""
from django.urls import path
from .views import SendOTPView, VerifyOTPView, DevVerifyOTPView

urlpatterns = [
    path('send/', SendOTPView.as_view(), name='otp-send'),
    path('verify/', VerifyOTPView.as_view(), name='otp-verify'),
    path('dev-verify/', DevVerifyOTPView.as_view(), name='otp-dev-verify'),
]
