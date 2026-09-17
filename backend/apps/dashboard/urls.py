from django.urls import path
from .views import (
    DashboardStatsView,
    DashboardActivityView,
    StudentDashboardStatsView,
    WishlistView,
    WishlistDetailView,
)

urlpatterns = [
    # ── Owner (admin panel) dashboard ──────────────────────────────────────
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard/activity/', DashboardActivityView.as_view(), name='dashboard-activity'),

    # ── Student (Flutter app) dashboard ────────────────────────────────────
    path('dashboard/student/stats/', StudentDashboardStatsView.as_view(), name='student-dashboard-stats'),

    # ── Wishlist ────────────────────────────────────────────────────────────
    path('wishlist/', WishlistView.as_view(), name='wishlist-list'),
    path('wishlist/<uuid:pk>/', WishlistDetailView.as_view(), name='wishlist-detail'),
]
