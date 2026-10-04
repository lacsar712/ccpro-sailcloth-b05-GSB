from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClothRollViewSet,
    CureLockView,
    DipRunViewSet,
    LoftViewSet,
    dashboard_stats,
)

router = DefaultRouter()
router.register("lofts", LoftViewSet, basename="loft")
router.register("rolls", ClothRollViewSet, basename="roll")
router.register("dips", DipRunViewSet, basename="dip")

urlpatterns = [
    path("dashboard/", dashboard_stats, name="dashboard"),
    path("settings/cure-lock/", CureLockView.as_view(), name="cure-lock"),
    path("", include(router.urls)),
]
