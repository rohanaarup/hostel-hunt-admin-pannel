from django.urls import path

from .views import StayEndView, StayVacateRequestView

urlpatterns = [
    path('stays/<uuid:pk>/vacate-request/', StayVacateRequestView.as_view(), name='stay-vacate-request'),
    path('stays/<uuid:pk>/end/', StayEndView.as_view(), name='stay-end'),
]
