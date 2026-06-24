from django.urls import path
from .views import DashboardStatsView, DashboardActivityView

urlpatterns = [
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard/activity/', DashboardActivityView.as_view(), name='dashboard-activity'),
]
