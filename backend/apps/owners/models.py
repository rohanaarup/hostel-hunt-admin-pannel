import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .managers import OwnerManager

class Owner(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('owner', 'Owner'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='owner_id')
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    display_name = models.CharField(max_length=150)
    
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='owner')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnerManager()

    USERNAME_FIELD = 'email'  # Can login with either email or phone, but Django requires this
    REQUIRED_FIELDS = ['display_name']

    class Meta:
        db_table = 'owners'

    def __str__(self):
        return self.display_name or self.email or self.phone_number or str(self.id)


class OTP(models.fields.Field):
    pass # Wait, let me replace this with proper model

class OTPRecord(models.Model):
    PURPOSE_CHOICES = (
        ('signup', 'Signup'),
        ('forgot_password', 'Forgot Password'),
    )
    
    identifier = models.CharField(max_length=150) # email or phone
    otp_code = models.CharField(max_length=128) # Hashed OTP
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    is_used = models.BooleanField(default=False)
    verification_token = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'otp_records'

    def __str__(self):
        return f"{self.identifier} - {self.purpose}"
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
