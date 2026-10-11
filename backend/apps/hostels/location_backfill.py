"""
Data migration helpers: link existing hostels to City / Locality rows built from their text.

Nothing is "corrected": each distinct city / locality text becomes one entry whose display name is
the same spelling with the case tidied (kondapur -> Kondapur, kphb -> KPHB). Staff can rename or add
aliases afterwards in Django admin. The legacy text columns are never modified.
The functions take the model classes so the migration can pass its historical models.
"""
import re

from .locations import match_key, normalise_slug

UNKNOWN = 'unknown'  # the word an earlier backfill put in empty localities


def display_name(raw):
    text = ' '.join((raw or '').split())
    if not text:
        return ''
    if text != text.lower() and text != text.upper():
        return text  # someone already chose a capitalisation
    words = []
    for word in text.lower().split(' '):
        if word.isalpha() and len(word) <= 5 and not re.search('[aeiou]', word):
            words.append(word.upper())  # acronyms such as KPHB
        else:
            words.append(word.capitalize())
    return ' '.join(words)


def link_hostels(Hostel, City, Locality):
    cities = {match_key(c.name): c for c in City.objects.all()}
    localities = {(loc.city_id, match_key(loc.name)): loc for loc in Locality.objects.all()}

    for hostel in Hostel.objects.all().order_by('created_at', 'pk'):
        city_key = match_key(hostel.city)
        if not city_key:
            continue
        city = cities.get(city_key)
        if city is None:
            name = display_name(hostel.city)
            city = City.objects.create(
                name=name, slug=normalise_slug(name), state=(hostel.state or '').strip(),
                is_active='test' not in name.lower(),
            )
            cities[city_key] = city

        locality = None
        locality_key = match_key(hostel.locality)
        if locality_key and locality_key != UNKNOWN:
            locality = localities.get((city.pk, locality_key))
            if locality is None:
                name = display_name(hostel.locality)
                locality = Locality.objects.create(city=city, name=name, slug=normalise_slug(name))
                localities[(city.pk, locality_key)] = locality

        Hostel.objects.filter(pk=hostel.pk).update(city_ref=city, locality_ref=locality)


def unlink_hostels(Hostel, City, Locality):
    """Reverse: clear the links and remove the entries (aliases go with their localities)."""
    Hostel.objects.update(city_ref=None, locality_ref=None)
    Locality.objects.all().delete()
    City.objects.all().delete()
