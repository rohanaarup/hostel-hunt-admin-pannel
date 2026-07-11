from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from .serializers import SendOTPSerializer, VerifyOTPSerializer
from .services import OTPService, OTPRateLimitException, OTPVerificationException
from .models import OTPRecord

User = get_user_model()


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        if User.objects.filter(email=email, is_verified=True).exists():
            return Response(
                {'success': False, 'message': 'Email already registered. Please login instead.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            OTPService.generate_and_send(email)
            return Response(
                {'success': True, 'message': 'OTP sent to your email. Valid for 5 minutes.'},
                status=status.HTTP_200_OK,
            )
        except OTPRateLimitException as e:
            return Response(
                {'success': False, 'message': e.reason},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"OTP Error: {str(e)}", exc_info=True)
            return Response(
                {'success': False, 'message': 'Failed to send OTP. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']

        try:
            OTPService.verify(email, otp_code)
            
            return Response(
                {'success': True, 'message': 'Email verified successfully!'},
                status=status.HTTP_200_OK,
            )
        except OTPVerificationException as e:
            return Response(
                {
                    'success': False,
                    'message': str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class DevVerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response(
                {'success': False, 'message': 'Not available in production.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'success': False, 'message': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email, is_verified=True).exists():
            return Response({'success': False, 'message': 'Email already registered.'}, status=status.HTTP_409_CONFLICT)

        now = timezone.now()
        OTPRecord.objects.filter(identifier=email, purpose='registration').delete()
        OTPRecord.objects.create(
            identifier=email,
            otp_code='dev_bypass_' + email,  
            purpose='registration',
            expires_at=now + timedelta(minutes=30),
            is_used=True,
        )

        return Response(
            {'success': True, 'message': 'Email verified for testing (dev mode).'},
            status=status.HTTP_200_OK,
        )
