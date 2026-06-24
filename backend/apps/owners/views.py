from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Owner
from .services import OTPService
from .serializers import (
    OwnerProfileSerializer, SendOtpSerializer, VerifyOtpSerializer,
    SignupSerializer, LoginSerializer, ResetPasswordSerializer
)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def success_response(data=None, message="Success", status_code=status.HTTP_200_OK):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status_code)

def error_response(errors, message="Error", status_code=status.HTTP_400_BAD_REQUEST):
    return Response({
        "success": False,
        "message": message,
        "errors": errors
    }, status=status_code)


class SendOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOtpSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            identifier_type = serializer.validated_data['identifier_type']
            purpose = serializer.validated_data['purpose']
            
            # If signup, check if already exists
            if purpose == 'signup':
                if identifier_type == 'email' and Owner.objects.filter(email=identifier).exists():
                    return error_response({"identifier": "Email already registered."})
                if identifier_type == 'phone' and Owner.objects.filter(phone_number=identifier).exists():
                    return error_response({"identifier": "Phone number already registered."})
            elif purpose == 'forgot_password':
                # If forgot_password, check if user exists
                exists = Owner.objects.filter(email=identifier).exists() if identifier_type == 'email' else Owner.objects.filter(phone_number=identifier).exists()
                if not exists:
                    return error_response({"identifier": "User not found."})

            code, record = OTPService.create_otp(identifier, purpose)
            
            sent, msg = OTPService.send_otp(identifier, code, purpose, identifier_type)
            if sent:
                return success_response(message="OTP sent successfully.")
            return error_response({"identifier": msg}, "Failed to send OTP.", status.HTTP_503_SERVICE_UNAVAILABLE)
            
        return error_response(serializer.errors)


class VerifyOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            code = serializer.validated_data['otp']
            purpose = serializer.validated_data['purpose']
            
            is_valid, message, token = OTPService.verify_otp(identifier, code, purpose)
            if is_valid:
                return success_response(data={"verification_token": str(token)}, message=message)
            return error_response({"otp": message})
            
        return error_response(serializer.errors)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            # OTP token was already validated securely in the serializer
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            profile = OwnerProfileSerializer(user).data
            
            return success_response(data={
                "tokens": tokens,
                "user": profile
            }, message="Registration successful.", status_code=status.HTTP_201_CREATED)
            
        return error_response(serializer.errors)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)
            profile = OwnerProfileSerializer(user).data
            
            return success_response(data={
                "tokens": tokens,
                "user": profile
            }, message="Login successful.")
            
        return error_response(serializer.errors)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response(message="Logged out successfully.")
        except Exception as e:
            return error_response({"detail": str(e)}, status_code=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            identifier_type = serializer.validated_data['identifier_type']
            # The verification_token was already validated securely in the serializer.
            
            user = None
            if identifier_type == 'email':
                user = Owner.objects.filter(email=identifier).first()
            else:
                user = Owner.objects.filter(phone_number=identifier).first()
                
            if user:
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                
                # Invalidate the used verification token so it can't be reused
                from .models import OTPRecord
                OTPRecord.objects.filter(verification_token=serializer.validated_data['verification_token']).update(is_used=True, verification_token=None)
                
                return success_response(message="Password reset successfully.")
            return error_response({"identifier": "User not found."})
            
        return error_response(serializer.errors)


class OwnerListView(APIView):
    permission_classes = [AllowAny]  # For now; lock down with IsAuthenticated + IsAdminUser in production

    def get(self, request):
        owners = Owner.objects.all().order_by('-created_at')
        serializer = OwnerProfileSerializer(owners, many=True)
        return success_response(data=serializer.data, message="Owners retrieved successfully.")


class OwnerProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = OwnerProfileSerializer(request.user)
        return success_response(data=serializer.data)
