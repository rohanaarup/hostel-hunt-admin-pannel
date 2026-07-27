from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum

from apps.hostels.models import Hostel
from apps.residents.models import Resident
from apps.bookings.models import Booking
from apps.payments.models import Payment

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        hostels = Hostel.objects.filter(owner=user)
        total_hostels = hostels.count()
        
        # Total residents (active only)
        total_residents = Resident.objects.filter(hostel__owner=user, status='active').count()
        
        # Occupancy rate calculation
        # total occupied beds / total capacity of all hostels
        total_beds = sum(h.total_beds for h in hostels)
        occupancy_rate = 0
        if total_beds > 0:
            occupancy_rate = int((total_residents / total_beds) * 100)
            
        payments = Payment.objects.filter(hostel__owner=user)
        # revenue collected = sum of amount_paid where status is 'paid' or 'partial'
        revenue_collected = payments.exclude(status='pending').aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        # revenue pending = sum of (amount_due - amount_paid)
        # Or simpler: sum of amount_due for pending/partial - sum of amount_paid
        pending_qs = payments.filter(status__in=['pending', 'partial', 'overdue'])
        amt_due = pending_qs.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        amt_paid = pending_qs.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        revenue_pending = amt_due - amt_paid
        
        pending_bookings = Booking.objects.filter(hostel__owner=user, status='pending').count()
        
        return Response({
            "success": True,
            "data": {
                "total_hostels": total_hostels,
                "total_residents": total_residents,
                "occupancy_rate": occupancy_rate,
                "revenue_collected": float(revenue_collected),
                "revenue_pending": float(revenue_pending),
                "pending_bookings": pending_bookings
            }
        })

class DashboardActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        activities = []
        
        recent_bookings = Booking.objects.filter(hostel__owner=user).order_by('-updated_at')[:10]
        for b in recent_bookings:
            activity_type = 'booking_request'
            title = 'New Booking Request'
            
            if b.status == 'confirmed':
                activity_type = 'booking_confirmed'
                title = 'Booking Confirmed'
            elif b.status == 'cancelled':
                activity_type = 'booking_cancelled'
                title = 'Booking Cancelled'
                
            activities.append({
                "activity_id": f"b_{b.id}",
                "type": activity_type,
                "title": title,
                "description": f"{b.student_name} requested a booking in {b.hostel.name}.",
                "timestamp": b.updated_at,
                "meta": {"booking_id": str(b.id)}
            })
            
        recent_payments = Payment.objects.filter(hostel__owner=user).order_by('-created_at')[:5]
        for p in recent_payments:
            if p.status == 'paid':
                activities.append({
                    "activity_id": f"p_{p.id}",
                    "type": "payment_received",
                    "title": "Payment Received",
                    "description": f"Received {p.amount_paid} from {p.resident_name}.",
                    "timestamp": p.created_at,
                    "meta": {"payment_id": str(p.id)}
                })
                
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:10]
        
        return Response({
            "success": True,
            "data": activities
        })
