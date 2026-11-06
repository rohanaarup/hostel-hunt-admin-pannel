from django.urls import path

from .views import DueRecordPaymentView, DueVoidPaymentView, StayEndView, StayVacateRequestView

urlpatterns = [
    path('stays/<uuid:pk>/vacate-request/', StayVacateRequestView.as_view(), name='stay-vacate-request'),
    path('stays/<uuid:pk>/end/', StayEndView.as_view(), name='stay-end'),
    path('stays/dues/<uuid:pk>/record-payment/', DueRecordPaymentView.as_view(), name='due-record-payment'),
    path('stays/dues/<uuid:pk>/void-payment/', DueVoidPaymentView.as_view(), name='due-void-payment'),
]
