from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from .models import Payment
from .serializers import PaymentSerializer

class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Owners can view payments. Usually payments are created via external hooks (Stripe/Razorpay) 
    or by the user.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return payments for hostels owned by the current user
        return Payment.objects.filter(hostel__owner=self.request.user)


class PaymentSummaryView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        payments = Payment.objects.filter(hostel__owner=request.user)
        
        total_revenue = payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        pending_amount = payments.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or 0
        completed_count = payments.filter(status='completed').count()
        pending_count = payments.filter(status='pending').count()
        
        return Response({
            "success": True,
            "data": {
                "total_revenue": total_revenue,
                "pending_amount": pending_amount,
                "completed_count": completed_count,
                "pending_count": pending_count
            }
        })
