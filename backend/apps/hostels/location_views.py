"""
GET /api/v1/cities/                       active cities that have at least one active hostel
GET /api/v1/cities/{slug}/localities/     active localities of a city that have at least one active hostel

Add ?include_empty=true to list every active entry (the admin wizard needs cities and localities
before any hostel exists there). Counts are of active hostels. These lists are small and
staff-managed, so they are not paginated.
"""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from .locations import match_key
from .models import City, Locality

_ACTIVE_HOSTELS = Q(hostels__is_active=True)


class CitySerializer(serializers.ModelSerializer):
    hostel_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = City
        fields = ['id', 'name', 'slug', 'state', 'hostel_count']


class LocalitySerializer(serializers.ModelSerializer):
    hostel_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Locality
        fields = ['id', 'name', 'slug', 'hostel_count']


def _include_empty(request):
    return request.query_params.get('include_empty', '').lower() in ('1', 'true', 'yes')


class CityListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CitySerializer
    pagination_class = None

    def get_queryset(self):
        qs = City.objects.filter(is_active=True).annotate(hostel_count=Count('hostels', filter=_ACTIVE_HOSTELS))
        if not _include_empty(self.request):
            qs = qs.filter(hostel_count__gt=0)
        return qs.order_by('name', 'id')


class CityLocalityListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = LocalitySerializer
    pagination_class = None

    def get_queryset(self):
        key = match_key(self.kwargs['slug'])
        city = next((c for c in City.objects.filter(is_active=True) if match_key(c.name) == key), None)
        city = city or get_object_or_404(City, slug=self.kwargs['slug'], is_active=True)
        qs = Locality.objects.filter(city=city, is_active=True).annotate(
            hostel_count=Count('hostels', filter=_ACTIVE_HOSTELS)
        )
        if not _include_empty(self.request):
            qs = qs.filter(hostel_count__gt=0)
        return qs.order_by('name', 'id')
