from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum

from apps.hostels.models import Hostel
from apps.rooms.models import Room
from apps.bookings.models import Booking
from apps.payments.models import Payment

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        hostels = Hostel.objects.filter(owner=user)
        has_registered_hostel = hostels.exists()
        
        rooms = Room.objects.filter(hostel__owner=user)
        total_rooms = rooms.count()
        
        # Simple definition: available if at least 1 bed available
        available_rooms = rooms.filter(available_beds__gt=0).count()
        occupied_rooms = total_rooms - available_rooms
        
        pending_requests = Booking.objects.filter(hostel__owner=user, status='pending').count()
        
        booked_users = Booking.objects.filter(
            hostel__owner=user, 
            status__in=['approved', 'checked_in']
        ).count()
        
        payments = Payment.objects.filter(hostel__owner=user)
        monthly_revenue = payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        pending_payments = payments.filter(status='pending').count()
        
        return Response({
            "success": True,
            "data": {
                "registered_hostel": has_registered_hostel,
                "total_rooms": total_rooms,
                "available_rooms": available_rooms,
                "occupied_rooms": occupied_rooms,
                "pending_requests": pending_requests,
                "booked_users": booked_users,
                "monthly_revenue": monthly_revenue,
                "pending_payments": pending_payments
            }
        })

class DashboardActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # We can aggregate recent bookings and payments as 'ActivityItem's
        activities = []
        
        recent_bookings = Booking.objects.filter(hostel__owner=user).order_by('-updated_at')[:10]
        for b in recent_bookings:
            activity_type = 'booking_request'
            title = 'New Booking Request'
            
            if b.status == 'approved':
                activity_type = 'booking_approved'
                title = 'Booking Approved'
            elif b.status == 'rejected':
                activity_type = 'booking_rejected'
                title = 'Booking Rejected'
                
            activities.append({
                "activity_id": f"b_{b.id}",
                "type": activity_type,
                "title": title,
                "description": f"{b.user_name} requested room {b.room_name} in {b.hostel.name}.",
                "timestamp": b.updated_at,
                "meta": {"booking_id": str(b.id)}
            })
            
        recent_payments = Payment.objects.filter(hostel__owner=user).order_by('-created_at')[:5]
        for p in recent_payments:
            if p.status == 'completed':
                activities.append({
                    "activity_id": f"p_{p.id}",
                    "type": "payment_received",
                    "title": "Payment Received",
                    "description": f"Received {p.amount} from {p.user_name}.",
                    "timestamp": p.created_at,
                    "meta": {"payment_id": str(p.id)}
                })
                
        # Sort combined list by timestamp descending and take top 10
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:10]
        
        return Response({
            "success": True,
            "data": activities
        })
