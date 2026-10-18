from django.apps import AppConfig

class HostelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hostels'

    def ready(self):
        # A saved city, locality, alias or hostel makes this process forget its cached public places lists.
        from django.db.models.signals import post_delete, post_save

        from . import places_cache
        from .models import City, Hostel, Locality, LocalityAlias
        for model in (City, Locality, LocalityAlias, Hostel):
            post_save.connect(places_cache.bump, sender=model, dispatch_uid=f'hh-places-{model.__name__}-save')
            post_delete.connect(places_cache.bump, sender=model, dispatch_uid=f'hh-places-{model.__name__}-delete')
