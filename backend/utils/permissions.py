from rest_framework import permissions

class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access/edit it.
    Assumes the model instance has an `owner` attribute, or IS the owner.
    """
    
    def has_object_permission(self, request, view, obj):
        import logging
        logger = logging.getLogger('django')
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        # Wait, the requirements state: "Owners may access only their own resources."
        # This implies even read access is restricted to the owner for dashboard resources.
        
        # If the object belongs to an Owner (e.g. Hostel, Room, etc.)
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
            
        # Fallback for nested relations like Room belonging to a Hostel
        if hasattr(obj, 'hostel'):
            return obj.hostel.owner == request.user
            
        # If the object itself is an Owner instance
        from apps.owners.models import Owner
        if isinstance(obj, Owner):
            return obj == request.user
            
        return False
