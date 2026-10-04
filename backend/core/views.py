from django.db import transaction
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .models import ClothRoll, CureLockSetting, DipRun, Loft
from .rules import can_change_roll_status, can_log_dip_for_roll
from .serializers import ClothRollSerializer, DipRunSerializer, LoftSerializer


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

    def perform_update(self, serializer):
        new_status = serializer.validated_data.get("status")
        with transaction.atomic():
            if new_status is not None:
                # 权威复查：锁住开关行与布卷行，防止绕过/并发改态
                CureLockSetting.get()
                CureLockSetting.objects.select_for_update().get(
                    pk=CureLockSetting.SINGLETON_ID
                )
                roll = ClothRoll.objects.select_for_update().get(pk=serializer.instance.pk)
                ok, msg = can_change_roll_status(roll, new_status)
                if not ok:
                    raise ValidationError({"status": msg})
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

    def perform_create(self, serializer):
        roll_id = serializer.validated_data["roll"].pk
        with transaction.atomic():
            # 权威复查：锁住开关行与该布卷行，两笔并发登记都会被挡下
            CureLockSetting.get()
            CureLockSetting.objects.select_for_update().get(
                pk=CureLockSetting.SINGLETON_ID
            )
            roll = ClothRoll.objects.select_for_update().get(pk=roll_id)
            ok, msg = can_log_dip_for_roll(roll)
            if not ok:
                raise ValidationError({"rollId": msg})
            serializer.save()


class CureLockView(APIView):
    """全站「已固化挂签只读」开关：登录可读，仅管理员可写。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        setting = CureLockSetting.get()
        return Response(
            {
                "locked": setting.locked,
                "updatedAt": setting.updated_at,
                "updatedBy": setting.updated_by.username if setting.updated_by else None,
            }
        )

    def _save(self, request):
        if request.user.role != User.ROLE_ADMIN:
            raise PermissionDenied("仅管理员可切换固化锁定")
        locked = request.data.get("locked")
        if not isinstance(locked, bool):
            raise ValidationError({"locked": "请提供布尔值 locked"})
        setting = CureLockSetting.get()
        setting.locked = locked
        setting.updated_by = request.user
        setting.save()
        return Response(
            {
                "locked": setting.locked,
                "updatedAt": setting.updated_at,
                "updatedBy": setting.updated_by.username if setting.updated_by else None,
            }
        )

    def patch(self, request):
        return self._save(request)

    def put(self, request):
        return self._save(request)


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
