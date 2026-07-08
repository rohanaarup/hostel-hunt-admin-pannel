from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
import re
from .models import Owner

def normalize_and_validate_identifier(identifier, identifier_type):
    if identifier_type == 'email':
        try:
            validate_email(identifier)
        except DjangoValidationError:
            raise serializers.ValidationError({"identifier": "Enter a valid email address."})
        return identifier.lower().strip()
    elif identifier_type == 'phone':
        clean_phone = re.sub(r'\s+', '', identifier)
        if not re.match(r'^[6-9]\d{9}$', clean_phone):
            raise serializers.ValidationError({"identifier": "Enter a valid 10-digit phone number."})
        return f"+91{clean_phone}"
    return identifier

class OwnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = [
            'id', 'email', 'phone_number', 'display_name', 
            'is_verified', 'is_active', 'profile_photo', 
            'role', 'created_at', 'updated_at'
        ]
        
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to owner_id to match frontend interface
        ret['owner_id'] = ret.pop('id')
        if ret.get('profile_photo'):
            ret['profile_photo_url'] = ret.pop('profile_photo')
        else:
            ret['profile_photo_url'] = None
        return ret


class SendOtpSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    identifier_type = serializers.ChoiceField(choices=['email', 'phone'])
    purpose = serializers.ChoiceField(choices=['signup', 'forgot_password'], required=False, default='signup')

    def validate(self, data):
        data['identifier'] = normalize_and_validate_identifier(data.get('identifier', ''), data.get('identifier_type'))
        return data


class VerifyOtpSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    identifier_type = serializers.ChoiceField(choices=['email', 'phone'])
    otp = serializers.CharField()
    purpose = serializers.ChoiceField(choices=['signup', 'forgot_password'], required=False, default='signup')

    def validate(self, data):
        data['identifier'] = normalize_and_validate_identifier(data.get('identifier', ''), data.get('identifier_type'))
        return data


class SignupSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    identifier_type = serializers.ChoiceField(choices=['email', 'phone'])
    display_name = serializers.CharField()
    password = serializers.CharField(write_only=True)
    verification_token = serializers.UUIDField(write_only=True)
    
    def validate(self, data):
        data['identifier'] = normalize_and_validate_identifier(data.get('identifier', ''), data.get('identifier_type'))
        identifier = data.get('identifier')
        identifier_type = data.get('identifier_type')
        
        # Check uniqueness
        if identifier_type == 'email':
            if Owner.objects.filter(email=identifier).exists():
                raise serializers.ValidationError({"identifier": "Email is already registered."})
        else:
            if Owner.objects.filter(phone_number=identifier).exists():
                raise serializers.ValidationError({"identifier": "Phone number is already registered."})
                
        # Validate verification_token — must be verified (OTP checked) but not yet consumed
        from .models import OTPRecord
        token = data.get('verification_token')
        if not OTPRecord.objects.filter(
            identifier=identifier,
            purpose='signup',
            verification_token=token,
            is_verified=True,
            is_used=False
        ).exists():
            raise serializers.ValidationError({"verification_token": "Invalid or expired verification token. Please verify your OTP again."})
                
        return data

    def create(self, validated_data):
        identifier = validated_data.pop('identifier')
        identifier_type = validated_data.pop('identifier_type')
        verification_token = validated_data.pop('verification_token', None)
        
        email = identifier if identifier_type == 'email' else None
        phone = identifier if identifier_type == 'phone' else None
        
        owner = Owner.objects.create_user(
            email=email,
            phone_number=phone,
            password=validated_data['password'],
            display_name=validated_data['display_name'],
            is_verified=True  # Because they already passed OTP step
        )
        
        # Consume the verification token so it can't be reused
        from .models import OTPRecord
        OTPRecord.objects.filter(
            identifier=identifier,
            purpose='signup',
            verification_token=verification_token,
            is_verified=True,
            is_used=False
        ).update(is_used=True, verification_token=None)
        
        return owner


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    identifier_type = serializers.ChoiceField(choices=['email', 'phone'])
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)

    def validate(self, data):
        data['identifier'] = normalize_and_validate_identifier(data.get('identifier', ''), data.get('identifier_type'))
        identifier = data.get('identifier')
        identifier_type = data.get('identifier_type')
        password = data.get('password')
        
        # Find the user first
        user = None
        if identifier_type == 'email':
            user = Owner.objects.filter(email=identifier).first()
        else:
            user = Owner.objects.filter(phone_number=identifier).first()
            
        if user is None:
            raise serializers.ValidationError({"detail": ["User not found with this identifier."]})
            
        # Standard authenticate expects 'username', so we must use the correct kwargs
        # Since we set USERNAME_FIELD='email', authenticate requires email
        if not user.check_password(password):
             raise serializers.ValidationError({"detail": ["Incorrect password."]})
             
        if not user.is_active:
             raise serializers.ValidationError({"detail": ["This account is inactive."]})
             
        if not user.is_verified:
             raise serializers.ValidationError({"detail": ["This account is not verified."]})

        data['user'] = user
        return data


class ResetPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    identifier_type = serializers.ChoiceField(choices=['email', 'phone'])
    verification_token = serializers.UUIDField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        data['identifier'] = normalize_and_validate_identifier(data.get('identifier', ''), data.get('identifier_type'))
        identifier = data.get('identifier')
        token = data.get('verification_token')
        from .models import OTPRecord
        
        if not OTPRecord.objects.filter(
            identifier=identifier,
            purpose='forgot_password',
            verification_token=token,
            is_verified=True,
            is_used=False
        ).exists():
            raise serializers.ValidationError({"verification_token": "Invalid or expired verification token."})
            
        return data
