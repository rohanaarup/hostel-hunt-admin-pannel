from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import MediaItem
from .serializers import MediaItemSerializer

class MediaUploadView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        # We assume frontend sends multipart/form-data
        serializer = MediaItemSerializer(data=request.data)
        if serializer.is_valid():
            # Check ownership if attached to a hostel or room
            hostel = serializer.validated_data.get('hostel')
            room = serializer.validated_data.get('room')
            
            from rest_framework.exceptions import PermissionDenied
            if hostel and hostel.owner != request.user:
                raise PermissionDenied("You do not own this hostel.")
            if room and room.hostel.owner != request.user:
                raise PermissionDenied("You do not own this room.")
                
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MediaDetailView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        try:
            item = MediaItem.objects.get(pk=pk)
            # Ownership check
            if item.hostel and item.hostel.owner != user:
                return None
            if item.room and item.room.hostel.owner != user:
                return None
            return item
        except MediaItem.DoesNotExist:
            return None

    def delete(self, request, pk, format=None):
        item = self.get_object(pk, request.user)
        if item is None:
             from rest_framework.exceptions import NotFound
             raise NotFound("Media not found or permission denied.")
             
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MediaReorderView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request):
        # Expects a list of { id: "uuid", order_index: 1 }
        items_data = request.data.get('items', [])
        
        updated = []
        for data in items_data:
            try:
                item = MediaItem.objects.get(pk=data['id'])
                # Ownership check
                if item.hostel and item.hostel.owner != request.user:
                    continue
                if item.room and item.room.hostel.owner != request.user:
                    continue
                    
                item.order_index = data.get('order_index', item.order_index)
                item.save(update_fields=['order_index'])
                updated.append(item)
            except MediaItem.DoesNotExist:
                continue
                
        return Response({"success": True, "updated": len(updated)})
