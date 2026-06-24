from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    SendOtpView, VerifyOtpView, RegisterView, LoginView, 
    LogoutView, ResetPasswordView, OwnerProfileView, OwnerListView
)

urlpatterns = [
    path('auth/send-otp/', SendOtpView.as_view(), name='send-otp'),
    path('auth/verify-otp/', VerifyOtpView.as_view(), name='verify-otp'),
    path('auth/resend-otp/', SendOtpView.as_view(), name='resend-otp'),  # Reuses send logic
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/forgot-password/', SendOtpView.as_view(), name='forgot-password'),  # Uses send-otp with purpose=forgot_password
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('auth/me/', OwnerProfileView.as_view(), name='auth-me'),
    path('owners/', OwnerListView.as_view(), name='owner-list'),
]
