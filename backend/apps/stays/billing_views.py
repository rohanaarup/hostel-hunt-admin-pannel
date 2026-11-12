"""
Billing configuration and its preview (Phase 9, the AdminBilling board).

    GET  /api/v1/hostels/<id>/billing/     a hostel's rent rule (the defaults when it has none)
    PUT  /api/v1/hostels/<id>/billing/     save it (owner of the hostel, or an admin)
    POST /api/v1/stays/billing/preview/    what a rule would do for one or more join dates (the admin never does the maths)

A saved rule applies to NEW stays only: a stay copies the rule when it is created (Stay.billing_snapshot) and keeps it, so
nothing here can change an existing stay. There is deliberately no "apply to existing stays" action.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Max, Min
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.tenancy.utils import get_tenant_scoped_object_or_404
from apps.hostels.models import Hostel
from apps.rooms.models import Room

from . import billing
from .models import HostelBillingConfig
from .views import IsTenantOwnerOrStaff

MAX_RENT = Decimal('1000000')
MAX_JOIN_DATES = 6
MAX_ROWS = 12
DEFAULT_ROWS = 5


# ------------------------------------------------------------------------------------------------------- the rule

class RuleCoreSerializer(serializers.Serializer):
    """The part of a rule that decides the dates and the first amount (what the preview needs)."""
    billing_mode = serializers.ChoiceField(choices=[billing.ANNIVERSARY, billing.FIXED_DAY])
    fixed_due_day = serializers.IntegerField(required=False, allow_null=True)
    fixed_due_last_day = serializers.BooleanField(required=False, default=False)
    first_period_policy = serializers.ChoiceField(choices=list(billing.FIRST_PERIOD_POLICIES), required=False, allow_null=True)

    def validate(self, attrs):
        mode = attrs['billing_mode']
        attrs['fixed_due_day'] = attrs.get('fixed_due_day')
        day, last = attrs['fixed_due_day'], attrs.get('fixed_due_last_day', False)
        policy = attrs.get('first_period_policy')
        problems = {}
        if mode == billing.FIXED_DAY:
            if day is None and not last:
                problems['fixed_due_day'] = 'Choose a due day from 1 to 28, or the last day of the month.'
            elif day is not None and last:
                problems['fixed_due_last_day'] = 'Choose a due day or the last day of the month, not both.'
            elif day is not None and not 1 <= day <= 28:
                problems['fixed_due_day'] = 'The due day must be from 1 to 28 (use the last-day option for the end of the month).'
            if policy is None:
                problems['first_period_policy'] = 'Choose how the first part-month is charged.'
        else:
            if day is not None or last:
                problems['billing_mode'] = 'A due day only applies to a fixed-day rule.'
        if problems:
            raise serializers.ValidationError(problems)
        if mode == billing.ANNIVERSARY:
            attrs['fixed_due_day'], attrs['fixed_due_last_day'], attrs['first_period_policy'] = None, False, None
        else:
            attrs['fixed_due_last_day'] = bool(last)
        return attrs


class BillingRuleSerializer(RuleCoreSerializer):
    payable_window_days = serializers.IntegerField(required=False, default=7, min_value=1, max_value=15)
    grace_days = serializers.IntegerField(required=False, default=0, min_value=0, max_value=15)


def _rule_payload(config, hostel):
    rents = Room.objects.filter(hostel=hostel, is_active=True).aggregate(low=Min('price_per_month'), high=Max('price_per_month'))
    anniversary = config.billing_mode == billing.ANNIVERSARY
    return {
        'hostel_id': str(hostel.id), 'hostel_name': hostel.name, 'locality': hostel.locality,
        'billing_mode': config.billing_mode,
        'fixed_due_day': config.fixed_due_day, 'fixed_due_last_day': config.fixed_due_last_day,
        'first_period_policy': None if anniversary else config.first_period_policy,
        'payable_window_days': config.payable_window_days, 'grace_days': config.grace_days,
        'monthly_rent': ({'min': str(rents['low']), 'max': str(rents['high'])} if rents['low'] is not None else None),
        'booking_payment_covers': 'FIRST_PERIOD_RENT',
        'applies_to': 'new_stays',
        'is_default': config.pk is None,
    }


class HostelBillingView(APIView):
    permission_classes = [IsAuthenticated, IsTenantOwnerOrStaff]

    def hostel(self, request, pk):
        hostel = get_object_or_404(Hostel, pk=pk) if request.user.is_staff else get_tenant_scoped_object_or_404(Hostel, pk, request)
        self.check_object_permissions(request, hostel)
        return hostel

    @extend_schema(summary="A hostel's billing rule", responses={200: dict})
    def get(self, request, pk):
        hostel = self.hostel(request, pk)
        return Response(_rule_payload(HostelBillingConfig.effective_for(hostel), hostel))

    @extend_schema(request=BillingRuleSerializer, responses={200: dict, 400: dict},
                   summary="Save a hostel's billing rule (applies to new stays only)")
    def put(self, request, pk):
        hostel = self.hostel(request, pk)
        data = BillingRuleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        config, _ = HostelBillingConfig.objects.update_or_create(hostel=hostel, defaults={
            'billing_mode': values['billing_mode'], 'fixed_due_day': values['fixed_due_day'],
            'fixed_due_last_day': values['fixed_due_last_day'],
            'first_period_policy': values['first_period_policy'] or billing.FULL_MONTH,
            'payable_window_days': values['payable_window_days'], 'grace_days': values['grace_days'],
        })
        return Response(_rule_payload(config, hostel))


# ------------------------------------------------------------------------------------------------------- preview

def _fmt(d):
    return f'{d.day} {d.strftime("%b")} {d.year}'


def inr(amount):
    """₹ with Indian digit grouping (6,000 and 1,00,000), as the board writes it; paise only when there are some."""
    amount = Decimal(amount)
    whole = amount == amount.to_integral_value()
    integer, _, decimals = f'{abs(amount):.2f}'.partition('.')
    head, tail = (integer[:-3], integer[-3:]) if len(integer) > 3 else ('', integer)
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    text = ','.join(groups + [tail])
    return f'₹{text}' if whole else f'₹{text}.{decimals}'


class PreviewSerializer(RuleCoreSerializer):
    monthly_rent = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'), max_value=MAX_RENT)
    join_date = serializers.DateField(required=False)
    join_dates = serializers.ListField(child=serializers.DateField(), required=False, max_length=MAX_JOIN_DATES)
    count = serializers.IntegerField(required=False, default=DEFAULT_ROWS, min_value=1, max_value=MAX_ROWS)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        dates = list(attrs.get('join_dates') or [])
        if attrs.get('join_date'):
            dates.insert(0, attrs['join_date'])
        if not dates:
            raise serializers.ValidationError({'join_date': 'Give a join date.'})
        attrs['dates'] = dates
        return attrs


class IsOwnerOrStaff(BasePermission):
    """Preview is for people who run hostels: an owner of at least one hostel, or an admin."""
    message = 'Only hostel owners and admins can preview a billing rule.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or Hostel.objects.filter(owner=user).exists()))


def _summary(join, mode, policy, rent, fixed_spec, first_amount):
    if mode == billing.ANNIVERSARY:
        return (f'Rent repeats on day {join.day} of every month. Short months use their last day, and every date is counted '
                f'from the join date.')
    following = billing.fixed_day_due_dates(join, fixed_spec, 1)[0]
    if billing.previous_fixed_due(join, fixed_spec) == join:
        return 'The student joins on the fixed day, so the first period is a full month.'
    first, full = billing.fixed_period_days(join, fixed_spec)
    if policy == billing.PRORATE:
        return (f'First period is prorated: {first} of {full} days = {inr(first_amount)}. From {_fmt(following)} the full rent '
                f'is due on the fixed day.')
    return (f'First period charges the full month ({inr(rent)}) even though the student joins part-way. From {_fmt(following)} '
            f'rent is due on the fixed day.')


def preview_for(join, mode, policy, rent, fixed_spec, count):
    periods = billing.build_periods(join, mode, policy or billing.FULL_MONTH, rent, fixed_spec, count)
    rows = []
    for index, period in enumerate(periods):
        rows.append({
            'label': 'Booking' if index == 0 else f'Rent {index}',
            'kind': 'BOOKING_PERIOD' if index == 0 else 'RENT',
            'period': f'{_fmt(period.start)} to {_fmt(period.end)}',
            'due': f'{_fmt(period.due_date)} (at booking)' if index == 0 else _fmt(period.due_date),
            'amount': inr(period.amount),
            'period_start': period.start.isoformat(), 'period_end': period.end.isoformat(),
            'due_date': period.due_date.isoformat(), 'amount_rupees': str(period.amount),
        })
    return {'join_date': join.isoformat(), 'rows': rows,
            'summary': _summary(join, mode, policy, rent, fixed_spec, periods[0].amount)}


class BillingPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    @extend_schema(request=PreviewSerializer, responses={200: dict, 400: dict},
                   summary='Preview a billing rule for join dates (nothing is saved)')
    def post(self, request):
        data = PreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        mode = values['billing_mode']
        fixed_spec = None
        if mode == billing.FIXED_DAY:
            fixed_spec = billing.LAST_DAY if values['fixed_due_last_day'] else values['fixed_due_day']
        results = [preview_for(join, mode, values.get('first_period_policy'), values['monthly_rent'], fixed_spec, values['count'])
                   for join in values['dates']]
        return Response({'results': results}, status=status.HTTP_200_OK)
