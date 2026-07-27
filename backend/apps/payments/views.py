from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone
from .models import Payment
from .serializers import PaymentSerializer, PaymentCreateSerializer
from apps.core.querysets import TenantScopedQuerysetMixin
from apps.core.utils import get_tenant_scoped_object_or_404

class PaymentListView(TenantScopedQuerysetMixin, generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()

    def get_queryset(self):
        # TenantScopedQuerysetMixin handles hostel__owner scoping via OWNER_LOOKUP.
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

class PaymentCreateView(generics.CreateAPIView):
    serializer_class = PaymentCreateSerializer
    permission_classes = [IsAuthenticated]

class PaymentMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        payment = get_tenant_scoped_object_or_404(Payment, pk, request)

        partial_amount = request.data.get('amount_paid')
        
        if partial_amount is not None:
            payment.amount_paid = partial_amount
            if float(payment.amount_paid) >= float(payment.amount_due):
                payment.status = 'paid'
            else:
                payment.status = 'partial'
        else:
            payment.amount_paid = payment.amount_due
            payment.status = 'paid'

        payment.paid_date = timezone.now().date()
        payment.marked_by = request.user
        payment.save(update_fields=['amount_paid', 'status', 'paid_date', 'marked_by', 'updated_at'])

        serializer = PaymentSerializer(payment)
        return Response({"success": True, "data": serializer.data})
