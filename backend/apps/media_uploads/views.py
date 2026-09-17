from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import MediaItem
from .serializers import MediaItemSerializer
from apps.core.tenancy.utils import get_scoped_object_or_404, is_tenant_owner
from apps.core.tenancy.querysets import tenant_scope_q


class MediaUploadView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # We assume frontend sends multipart/form-data
        serializer = MediaItemSerializer(data=request.data)
        if serializer.is_valid():
            # MediaItem can be attached to a hostel and/or a room; either
            # parent must belong to the requesting user (mirrors
            # MediaItem.OWNER_LOOKUP = ("hostel__owner", "room__hostel__owner")).
            hostel = serializer.validated_data.get('hostel')
            room = serializer.validated_data.get('room')

            if hostel and not is_tenant_owner(hostel, request.user):
                raise PermissionDenied("You do not own this hostel.")
            if room and not is_tenant_owner(room, request.user):
                raise PermissionDenied("You do not own this room.")

            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MediaDetailView(views.APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, format=None):
        # Http404 here is handled by DRF's default exception handler and
        # rendered as a plain 404 — same "not found or not yours,
        # indistinguishable" behaviour as before.
        item = get_scoped_object_or_404(MediaItem, pk, request, kind="tenant")
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MediaReorderView(views.APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        # Expects a list of { id: "uuid", order_index: 1 }
        items_data = request.data.get('items', [])

        # Scoped once up front, same shape as any other tenant-scoped
        # list — items outside this queryset are silently skipped below,
        # same fail-closed behaviour as the previous per-item try/except.
        requested_ids = [d.get('id') for d in items_data]
        owned_items = {
            str(item.id): item
            for item in MediaItem.objects.filter(id__in=requested_ids)
                                          .filter(tenant_scope_q(MediaItem, request.user))
        } if requested_ids else {}

        updated = []
        for data in items_data:
            item = owned_items.get(str(data.get('id')))
            if item is None:
                continue
            item.order_index = data.get('order_index', item.order_index)
            item.save(update_fields=['order_index'])
            updated.append(item)

        return Response({"success": True, "updated": len(updated)})
