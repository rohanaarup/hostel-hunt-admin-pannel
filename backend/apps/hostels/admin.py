from django.contrib import admin

from .models import City, Hostel, Locality, LocalityAlias


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'locality', 'owner_name', 'gender_type', 'is_active', 'is_verified')
    list_filter = ('gender_type', 'is_active', 'is_verified', 'city_ref')
    search_fields = ('name', 'owner_name', 'city', 'locality', 'id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    autocomplete_fields = ('city_ref', 'locality_ref')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')


class LocalityAliasInline(admin.TabularInline):
    model = LocalityAlias
    extra = 1
    fields = ('alias_slug',)


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'slug', 'is_active')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'slug', 'city__name')
    inlines = [LocalityAliasInline]
