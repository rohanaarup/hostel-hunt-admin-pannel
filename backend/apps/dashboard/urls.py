from django.urls import path
from .views import (
    DashboardStatsView,
    DashboardActivityView,
    StudentDashboardStatsView,
    WishlistView,
    WishlistIdsView,
    WishlistHostelView,
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
    path('wishlist/ids/', WishlistIdsView.as_view(), name='wishlist-ids'),
    path('wishlist/hostel/<uuid:hostel_id>/', WishlistHostelView.as_view(), name='wishlist-hostel'),
    path('wishlist/<uuid:pk>/', WishlistDetailView.as_view(), name='wishlist-detail'),
]
