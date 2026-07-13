from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from .models import Booking
from .serializers import BookingSerializer

class BookingViewSet(viewsets.ModelViewSet):
    """
    Owners can only read bookings. Creation is typically done by the user in the Flutter app.
    We expose custom endpoints for approve/reject.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return bookings for hostels owned by the current user
        return Booking.objects.filter(hostel__owner=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(
            user_id=str(user.id),
            user_name=getattr(user, 'display_name', user.email),
            user_email=user.email,
            user_phone=getattr(user, 'phone_number', ''),
            user_profile_photo=None
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'pending':
            return Response({"error": "Can only approve pending bookings."}, status=status.HTTP_400_BAD_REQUEST)
            
        booking.status = 'approved'
        booking.save(update_fields=['status'])
        
        # We could also decrement available beds in the room here.
        
        serializer = self.get_serializer(booking)
        return Response({"success": True, "data": serializer.data})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'pending':
            return Response({"error": "Can only reject pending bookings."}, status=status.HTTP_400_BAD_REQUEST)
            
        booking.status = 'rejected'
        booking.save(update_fields=['status'])
        
        serializer = self.get_serializer(booking)
        return Response({"success": True, "data": serializer.data})
