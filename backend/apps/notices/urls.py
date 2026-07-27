from django.urls import path
from .views import NoticeListView, NoticeCreateView, NoticeUpdateView, NoticeDeleteView

urlpatterns = [
    path('notices/', NoticeListView.as_view(), name='notice-list'),
    path('notices/create/', NoticeCreateView.as_view(), name='notice-create'),
    path('notices/<uuid:pk>/', NoticeUpdateView.as_view(), name='notice-update'),
    path('notices/<uuid:pk>/delete/', NoticeDeleteView.as_view(), name='notice-delete'),
]
