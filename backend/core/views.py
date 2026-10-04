from django.db import transaction
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.views import APIView

from .models import ClothRoll, DipRun, Loft, SystemSetting
from .permissions import IsAdminRole
from .rules import LOCK_MSG_DIP, LOCK_MSG_STATUS, cured_lock_on
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    SystemSettingSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    @transaction.atomic
    def perform_update(self, serializer):
        # 行锁下以库内最新状态再判一次，防止校验与落库之间状态/开关变化
        if "status" in serializer.validated_data and serializer.instance is not None:
            locked = ClothRoll.objects.select_for_update().get(pk=serializer.instance.pk)
            new_status = serializer.validated_data["status"]
            if (
                locked.status == ClothRoll.STATUS_CURED
                and new_status != ClothRoll.STATUS_CURED
                and cured_lock_on()
            ):
                raise ValidationError({"status": LOCK_MSG_STATUS})
        serializer.save()


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        # 锁住布卷行：并发登记在此排队，逐笔按最新状态与开关判定，两笔都挡
        roll = ClothRoll.objects.select_for_update().get(
            pk=serializer.validated_data["roll"].pk
        )
        if roll.status == ClothRoll.STATUS_CURED and cured_lock_on():
            raise PermissionDenied(LOCK_MSG_DIP)
        serializer.save()


class CureLockView(APIView):
    """全站「已固化挂签只读」开关：登录用户可读，仅管理员可改。"""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        return Response(SystemSettingSerializer(SystemSetting.get()).data)

    def patch(self, request):
        serializer = SystemSettingSerializer(
            SystemSetting.get(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
