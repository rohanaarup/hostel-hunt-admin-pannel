from django.db.models import Count, DecimalField, IntegerField, Max, Min, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.tenancy.permissions import IsTenantOwner
from apps.core.tenancy.querysets import tenant_scope_q
from apps.media_uploads.models import MediaItem
from apps.rooms.models import Room
from utils.pagination import CustomPageNumberPagination

from .locations import match_key, resolve_city, resolve_localities
from .models import Hostel, Locality
from .serializers import HostelListSerializer, HostelSerializer


class PublicHostelSerializer(HostelSerializer):
    """Safe read-only serializer for the public hostel detail."""
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
        ret = serializers.ModelSerializer.to_representation(self, instance)
        # Rename id → hostel_id to match Flutter model expectation
        if 'id' in ret:
            ret['hostel_id'] = ret.pop('id')
        return ret


class HostelPagination(CustomPageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


def _room_stat(aggregate):
    """A per-hostel room aggregate as a subquery. Unlike a JOIN + GROUP BY it leaves the hostels query
    ungrouped, so the pagination count is a plain COUNT over the filtered hostels."""
    rooms = Room.objects.filter(hostel=OuterRef('pk')).order_by().values('hostel')
    return rooms.annotate(value=aggregate).values('value')[:1]


def apply_list_filters(qs, params):
    """Filters shared by every list scope. Parameters: gender_type, city, locality, search, amenity."""
    gender = params.get('gender_type')
    if gender:
        qs = qs.filter(gender_type=gender)

    city_value = (params.get('city') or '').strip()
    city = resolve_city(city_value) if city_value else None
    if city is not None:
        # Linked hostels by id; rows not linked yet by their legacy text.
        qs = qs.filter(Q(city_ref=city) | Q(city_ref__isnull=True, city__iexact=city.name))
    elif city_value:
        qs = qs.filter(city_ref__isnull=True, city__iexact=city_value)

    locality_value = (params.get('locality') or '').strip()
    if locality_value:
        matches = resolve_localities(locality_value, city)
        if matches:
            qs = qs.filter(locality_ref__in=matches)
        else:  # not a known place: legacy text match, only for hostels that have no link yet
            qs = qs.filter(locality_ref__isnull=True, locality__icontains=locality_value)

    search = (params.get('search') or '').strip()
    if len(search) >= 2:
        condition = Q(name__icontains=search) | Q(locality__icontains=search) | Q(address__icontains=search)
        # Another spelling of a locality (staff add them, e.g. in Telugu or Hindi) finds its hostels too.
        matches = resolve_localities(search)
        if matches:
            condition |= Q(locality_ref__in=matches)
        qs = qs.filter(condition)

    amenity = (params.get('amenity') or '').strip()
    if amenity:
        qs = qs.filter(amenities__icontains=f'"{amenity}"')
    return qs


def public_hostel_queryset():
    """Active hostels in active cities, with price range, counts and cover image as annotations (no
    per-row queries). The public list and the saved-hostels list are both built on it."""
    cover = MediaItem.objects.filter(hostel=OuterRef('pk')).order_by('order_index', '-created_at').values('file_url')[:1]
    return (
        Hostel.objects
        .filter(is_active=True)
        .filter(Q(city_ref__isnull=True) | Q(city_ref__is_active=True))
        .annotate(
            price_from=Subquery(_room_stat(Min('price_per_month')), output_field=DecimalField(max_digits=10, decimal_places=2)),
            price_to=Subquery(_room_stat(Max('price_per_month')), output_field=DecimalField(max_digits=10, decimal_places=2)),
            room_count=Coalesce(Subquery(_room_stat(Count('pk')), output_field=IntegerField()), 0),
            bed_count=Coalesce(Subquery(_room_stat(Sum('bed_count')), output_field=IntegerField()), 0),
            cover_image=Subquery(cover),
        )
    )


LIST_PARAMETERS = [
    OpenApiParameter('city', str, description='City name, slug or id (case, spaces and punctuation ignored). Without a locality: the whole city.'),
    OpenApiParameter('locality', str, description='Locality name, slug, alias (e.g. a second spelling) or id. Best combined with city.'),
    OpenApiParameter('search', str, description='At least 2 characters; matches name, locality or address, ignoring case.'),
    OpenApiParameter('amenity', str, description="One amenity from the hostel's list, e.g. ac."),
    OpenApiParameter('gender_type', str, enum=['boys', 'girls', 'co_living']),
    OpenApiParameter('scope', str, enum=['public', 'mine', 'all'], description="public (default, same for everyone), mine (the signed-in owner's hostels), all (staff)."),
]


@extend_schema_view(list=extend_schema(parameters=LIST_PARAMETERS))
class HostelViewSet(viewsets.ModelViewSet):
    """
    GET /hostels/                      public list: active hostels, the same for everyone, token or not
    GET /hostels/?scope=mine           the signed-in owner's own hostels (including inactive)
    GET /hostels/?scope=all            every hostel (staff only)
    GET /hostels/{id}/                 public detail of an active hostel; owners can also open their own
    POST/PUT/PATCH/DELETE              owner scoped, as before

    Public list parameters: city, locality (name, slug, alias or id), search (name, locality, address),
    amenity, gender_type, page, page_size (default 10, maximum 50). Ordered newest first, then by id,
    so pages never repeat or skip a hostel.
    """
    serializer_class = HostelSerializer
    pagination_class = HostelPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'localities']:
            return [AllowAny()]
        return [IsAuthenticated(), IsTenantOwner()]

    def _scope(self):
        scope = (self.request.query_params.get('scope') or 'public').lower()
        if scope in ('mine', 'all'):
            if not self.request.user.is_authenticated:
                raise NotAuthenticated()
            if scope == 'all' and not self.request.user.is_staff:
                raise PermissionDenied('Only staff can list all hostels.')
        return scope if scope in ('mine', 'all') else 'public'

    def get_serializer_class(self):
        if self.action == 'list' and self._scope() == 'public':
            return HostelListSerializer
        return HostelSerializer

    def get_queryset(self):
        user = self.request.user
        if self.action == 'list':
            scope = self._scope()
            if scope == 'mine':
                qs = Hostel.objects.filter(tenant_scope_q(Hostel, user)).prefetch_related('rooms', 'media')
            elif scope == 'all':
                qs = Hostel.objects.all().prefetch_related('rooms', 'media')
            else:
                qs = self._public_list_queryset()
            return apply_list_filters(qs, self.request.query_params).order_by('-created_at', 'id')

        if self.action == 'retrieve':
            visible = Q(is_active=True, city_ref__isnull=True) | Q(is_active=True, city_ref__is_active=True)
            if user.is_authenticated:
                visible |= Q(tenant_scope_q(Hostel, user))
            return Hostel.objects.filter(visible).prefetch_related('rooms', 'media')

        # Writes and other owner actions: only the owner's hostels, as before.
        if not user.is_authenticated:
            return Hostel.objects.none()
        return Hostel.objects.filter(tenant_scope_q(Hostel, user)).prefetch_related('rooms', 'media')

    def _public_list_queryset(self):
        return public_hostel_queryset()

    def retrieve(self, request, *args, **kwargs):
        hostel = self.get_object()
        owns = request.user.is_authenticated and Hostel.objects.filter(
            tenant_scope_q(Hostel, request.user), pk=hostel.pk
        ).exists()
        serializer_class = HostelSerializer if owns else PublicHostelSerializer
        return Response(serializer_class(hostel, context=self.get_serializer_context()).data)

    def perform_create(self, serializer):
        # Auto-set the owner to the current user
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['get'], url_path='localities', permission_classes=[AllowAny])
    def localities(self, request):
        """
        GET /api/v1/hostels/localities/?city=Hyderabad   (kept for older apps; prefer /cities/{slug}/localities/)
        Response: [{"locality": "Kondapur", "count": 6}, ...] sorted by count descending, active hostels only.
        """
        city_value = (request.query_params.get('city') or '').strip()
        city = resolve_city(city_value) if city_value else None

        if city is not None:
            rows = (
                Locality.objects.filter(city=city, is_active=True)
                .annotate(count=Count('hostels', filter=Q(hostels__is_active=True)))
                .filter(count__gt=0)
                .order_by('-count', 'name')
            )
            return Response([{'locality': row.name, 'count': row.count} for row in rows])

        # No (or an unknown) city: the old behaviour over the legacy text.
        qs = Hostel.objects.filter(is_active=True)
        if city_value:
            qs = qs.filter(city__iexact=city_value)
        counts = {}
        for text in qs.values_list('locality', flat=True):
            if text and match_key(text) != 'unknown':
                counts[text] = counts.get(text, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return Response([{'locality': name, 'count': count} for name, count in ordered])
