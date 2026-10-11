import uuid
from django.db import models
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from apps.core.models import GlobalModel, TenantScopedModel
from .locations import match_key, normalise_slug



GENDER_CHOICES = (
    ('boys', 'Boys'),
    ('girls', 'Girls'),
    ('co_living', 'Co-Living'),
)

class City(GlobalModel):
    """A city people can pick. Shared reference data (no owner), staff-managed, so spelling variants cannot multiply."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    state = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cities'
        ordering = ['name']
        verbose_name_plural = 'cities'

    def __str__(self):
        return self.name

    def clean(self):
        if not self.slug:
            self.slug = normalise_slug(self.name)
        key = match_key(self.name)
        if not key:
            raise ValidationError({'name': 'A city needs a name.'})
        clash = [c for c in City.objects.exclude(pk=self.pk) if match_key(c.name) == key]
        if clash:
            raise ValidationError({'name': f'"{clash[0].name}" already exists (case, spaces and punctuation are ignored).'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Locality(GlobalModel):
    """A neighbourhood inside a city."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='localities')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'localities'
        ordering = ['name']
        verbose_name_plural = 'localities'
        constraints = [models.UniqueConstraint(fields=['city', 'slug'], name='locality_unique_slug_per_city')]

    def __str__(self):
        return f'{self.name}, {self.city.name}'

    def clean(self):
        if not self.slug:
            self.slug = normalise_slug(self.name)
        key = match_key(self.name)
        if not key:
            raise ValidationError({'name': 'A locality needs a name.'})
        for other in Locality.objects.filter(city=self.city).exclude(pk=self.pk):
            if match_key(other.name) == key:
                raise ValidationError({'name': f'"{other.name}" already exists in {self.city.name}.'})
        for alias in LocalityAlias.objects.filter(city=self.city).exclude(locality=self.pk):
            if match_key(alias.alias_slug) == key:
                raise ValidationError({'name': f'"{self.name}" is already an alias of {alias.locality.name}.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class LocalityAlias(GlobalModel):
    """Another spelling of a locality (Dilsuknagar for Dilsukhnagar). Matched like the name."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    locality = models.ForeignKey(Locality, on_delete=models.CASCADE, related_name='aliases')
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='locality_aliases', editable=False)
    alias_slug = models.CharField(max_length=280, help_text='The other spelling, e.g. "Dilsuknagar".')

    class Meta:
        db_table = 'locality_aliases'
        verbose_name_plural = 'locality aliases'

    def __str__(self):
        return f'{self.alias_slug} -> {self.locality.name}'

    def clean(self):
        self.city = self.locality.city
        key = match_key(self.alias_slug)
        if not key:
            raise ValidationError({'alias_slug': 'An alias needs a value.'})
        for loc in Locality.objects.filter(city=self.city):
            if match_key(loc.name) == key:
                raise ValidationError({'alias_slug': f'"{loc.name}" is already a locality in {self.city.name}.'})
        for other in LocalityAlias.objects.filter(city=self.city).exclude(pk=self.pk):
            if match_key(other.alias_slug) == key:
                raise ValidationError({'alias_slug': f'Already an alias of {other.locality.name}.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Hostel(TenantScopedModel):
    OWNER_LOOKUP = "owner"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='hostel_id')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hostels')
    name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20)
    email = models.EmailField()
    
    # Legacy free text, kept for one release and kept in step with the links below.
    locality = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100, db_index=True)
    # The canonical place. Nullable until every row is linked.
    city_ref = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name='hostels')
    locality_ref = models.ForeignKey(Locality, null=True, blank=True, on_delete=models.SET_NULL, related_name='hostels')
    state = models.CharField(max_length=100, db_index=True)
    pincode = models.CharField(max_length=20)
    landmark = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    google_maps_url = models.URLField(max_length=500, null=True, blank=True)
    
    gender_type = models.CharField(max_length=20, choices=GENDER_CHOICES, db_index=True)
    total_floors = models.PositiveIntegerField(default=1)
    total_rooms = models.PositiveIntegerField(default=0)
    total_beds = models.PositiveIntegerField(default=0)
    occupancy_types = models.JSONField(default=list) # List of strings e.g. ['single', 'double']
    
    description = models.TextField(null=True, blank=True)
    rules = models.TextField(null=True, blank=True)
    check_in_policy = models.CharField(max_length=255, null=True, blank=True)
    check_out_policy = models.CharField(max_length=255, null=True, blank=True)
    
    amenities = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostels'
        ordering = ['-created_at']
        indexes = [
            # locality is filtered with __icontains (partial match); a
            # plain B-tree index on city/state above doesn't help that,
            # so use a trigram GIN index instead. Requires the pg_trgm
            # extension (added via migration — see 0004_*.py).
            GinIndex(fields=['locality'], name='hostel_locality_trgm', opclasses=['gin_trgm_ops']),
            # The public list: active hostels of a city / locality, newest first.
            models.Index(fields=['is_active', 'city_ref', 'locality_ref', '-created_at'], name='hostel_public_list_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"
