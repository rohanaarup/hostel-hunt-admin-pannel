from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Min, Max, Sum, OuterRef, Subquery
from .models import Hostel
from .serializers import HostelSerializer, HostelListSerializer
from apps.media_uploads.models import MediaItem
from apps.core.tenancy.permissions import IsTenantOwner
from apps.core.tenancy.querysets import tenant_scope_q


class PublicHostelSerializer(HostelSerializer):
    """Safe read-only serializer for unauthenticated public listing."""
    class Meta(HostelSerializer.Meta):
        # Explicitly list public-safe fields (exclude 'owner' UUID)
        fields = [
            'id', 'name', 'owner_name', 'contact_number', 'email',
            'locality', 'address', 'city', 'state', 'pincode', 'landmark',
            'latitude', 'longitude', 'google_maps_url',
            'gender_type', 'total_floors', 'total_rooms', 'total_beds',
            'occupancy_types', 'description', 'rules',
            'check_in_policy', 'check_out_policy',
            'amenities', 'is_active', 'is_verified',
            'created_at', 'updated_at',
            'rooms', 'media',
        ]

    def to_representation(self, instance):
        # Skip parent's to_representation (which tries to pop 'owner')
        # Call grandparent directly
        from rest_framework import serializers
        ret = serializers.ModelSerializer.to_representation(self, instance)
        # Rename id → hostel_id to match Flutter model expectation
        if 'id' in ret:
            ret['hostel_id'] = ret.pop('id')
        return ret


class HostelViewSet(viewsets.ModelViewSet):
    serializer_class = HostelSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'localities']:
            return [AllowAny()]
        return [IsAuthenticated(), IsTenantOwner()]

    def get_serializer_class(self):
        if not self.request.user.is_authenticated:
            if self.action == 'list':
                return HostelListSerializer
            if self.action == 'retrieve':
                return PublicHostelSerializer
        return HostelSerializer

    def get_queryset(self):
        # For public unauthenticated requests, return all active hostels
        if self.action in ['list', 'retrieve'] and not self.request.user.is_authenticated:
            qs = Hostel.objects.filter(is_active=True)

            # Filter by gender_type
            gender = self.request.query_params.get('gender_type')
            if gender:
                qs = qs.filter(gender_type=gender)

            # Filter by city (case-insensitive exact match)
            city = self.request.query_params.get('city')
            if city:
                qs = qs.filter(city__iexact=city)

            # Filter by locality (case-insensitive partial match)
            locality = self.request.query_params.get('locality')
            if locality:
                qs = qs.filter(locality__icontains=locality)

            if self.action == 'list':
                # Lightweight list: aggregate room/bed counts and price range,
                # and pull a single cover image via subquery — no full
                # rooms/media prefetch (see HostelListSerializer).
                cover_subquery = MediaItem.objects.filter(
                    hostel=OuterRef('pk')
                ).order_by('order_index', '-created_at').values('file_url')[:1]

                qs = qs.annotate(
                    price_from=Min('rooms__price_per_month'),
                    price_to=Max('rooms__price_per_month'),
                    room_count=Count('rooms', distinct=True),
                    bed_count=Sum('rooms__bed_count'),
                    cover_image=Subquery(cover_subquery),
                )
            else:
                qs = qs.prefetch_related('rooms', 'media')

            return qs

        # For authenticated owners (and all other actions), return only their hostels
        if not self.request.user.is_authenticated:
            return Hostel.objects.none()
        return Hostel.objects.filter(
            tenant_scope_q(Hostel, self.request.user)
        ).prefetch_related('rooms', 'media')

    def perform_create(self, serializer):
        # Auto-set the owner to the current user
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['get'], url_path='localities', permission_classes=[AllowAny])
    def localities(self, request):
        """
        GET /api/v1/hostels/localities/?city=Hyderabad
        Returns distinct localities with hostel counts for the given city.
        Response: [{"locality": "Kondapur", "count": 6}, ...]
        Sorted by count descending.
        """
        city = request.query_params.get('city', '')
        qs = Hostel.objects.filter(is_active=True)
        if city:
            qs = qs.filter(city__iexact=city)

        localities = (
            qs
            .values('locality')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        data = [
            {'locality': item['locality'], 'count': item['count']}
            for item in localities
            if item['locality']  # exclude empty/null locality values
        ]

        return Response(data)
