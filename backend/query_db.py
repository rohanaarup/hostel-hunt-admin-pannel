import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.hostels.models import Hostel
from django.db.models import Count

cities = Hostel.objects.values('city').annotate(count=Count('id')).order_by('-count')
print('CITIES:')
for c in cities:
    print(f"  {c['city']} ({c['count']})")

localities = Hostel.objects.values('locality').annotate(count=Count('id')).order_by('-count')
print('LOCALITIES:')
for l in localities:
    print(f"  {l['locality']} ({l['count']})")

print('TOTAL HOSTELS:', Hostel.objects.count())
