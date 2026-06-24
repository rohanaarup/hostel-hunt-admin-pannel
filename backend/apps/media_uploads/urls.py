from django.urls import path
from .views import MediaUploadView, MediaDetailView, MediaReorderView

urlpatterns = [
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
    path('media/<uuid:pk>/', MediaDetailView.as_view(), name='media-detail'),
    path('media/reorder/', MediaReorderView.as_view(), name='media-reorder'),
]
