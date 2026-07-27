from django.urls import path
from .views import ResidentListView, ResidentCreateView, ResidentMarkVacatedView

urlpatterns = [
    path('residents/', ResidentListView.as_view(), name='resident-list'),
    path('residents/create/', ResidentCreateView.as_view(), name='resident-create'),
    path('residents/<uuid:pk>/mark-vacated/', ResidentMarkVacatedView.as_view(), name='resident-mark-vacated'),
]
