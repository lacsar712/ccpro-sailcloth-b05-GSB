import threading
from decimal import Decimal

from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient, APITransactionTestCase

from accounts.models import User
from core.models import ClothRoll, CureLockSetting, DipRun, Loft


def dip_payload(roll_id, cure_hours=None):
    return {
        "rollId": roll_id,
        "startedAt": timezone.now().isoformat(),
        "resinPct": "28.00",
        "cureHours": cure_hours,
        "notes": "",
    }


class CureLockTests(APITransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_t", password="x", role=User.ROLE_ADMIN
        )
        self.worker = User.objects.create_user(
            username="worker_t", password="x", role=User.ROLE_WORKER
        )
        self.loft = Loft.objects.create(name="测试帆布间")
        self.raw = ClothRoll.objects.create(
            loft=self.loft, roll_code="RAW-1", status=ClothRoll.STATUS_RAW
        )
        self.dipping = ClothRoll.objects.create(
            loft=self.loft, roll_code="DIP-1", status=ClothRoll.STATUS_DIPPING
        )
        self.cured = ClothRoll.objects.create(
            loft=self.loft, roll_code="CUR-1", status=ClothRoll.STATUS_CURED
        )
        DipRun.objects.create(
            roll=self.cured,
            started_at=timezone.now(),
            resin_pct=Decimal("28.0"),
            cure_hours=Decimal("14.0"),
        )

    def as_admin(self):
        self.client.force_authenticate(self.admin)

    def as_worker(self):
        self.client.force_authenticate(self.worker)

    # ---------- 开关读取 / 持久化 / 权限 ----------

    def test_default_unlocked(self):
        self.as_worker()
        resp = self.client.get("/api/cure-lock/")
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.data["locked"], False)

    def test_anonymous_denied(self):
        resp = self.client.get("/api/cure-lock/")
        self.assertEqual(resp.status_code, 401)

    def test_admin_toggle_persists(self):
        self.as_admin()
        resp = self.client.patch("/api/cure-lock/", {"locked": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.data["locked"], True)

        # “刷新后仍有效”：新请求、直接查库
        resp = self.client.get("/api/cure-lock/")
        self.assertIs(resp.data["locked"], True)
        setting = CureLockSetting.get()
        self.assertTrue(setting.locked)
        self.assertEqual(setting.updated_by, self.admin)

        resp = self.client.patch("/api/cure-lock/", {"locked": False}, format="json")
        self.assertIs(resp.data["locked"], False)
        self.assertFalse(CureLockSetting.get().locked)

    def test_worker_can_read_but_not_write(self):
        self.as_worker()
        resp = self.client.get("/api/cure-lock/")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.patch("/api/cure-lock/", {"locked": True}, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(CureLockSetting.get().locked)

    def test_invalid_payload_rejected(self):
        self.as_admin()
        resp = self.client.patch("/api/cure-lock/", {"locked": "yes"}, format="json")
        self.assertEqual(resp.status_code, 400)

    # ---------- 锁定后的业务拦截 ----------

    def _lock(self):
        self.as_admin()
        self.client.patch("/api/cure-lock/", {"locked": True}, format="json")

    def test_locked_blocks_dip_for_cured(self):
        self._lock()
        self.as_worker()
        before = DipRun.objects.count()
        resp = self.client.post("/api/dips/", dip_payload(self.cured.id), format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("rollId", resp.data)
        self.assertEqual(DipRun.objects.count(), before)

    def test_locked_blocks_status_revert_from_cured(self):
        self._lock()
        self.as_worker()
        for target in (ClothRoll.STATUS_RAW, ClothRoll.STATUS_DIPPING):
            resp = self.client.patch(
                f"/api/rolls/{self.cured.id}/", {"status": target}, format="json"
            )
            self.assertEqual(resp.status_code, 400)
            self.cured.refresh_from_db()
            self.assertEqual(self.cured.status, ClothRoll.STATUS_CURED)

    def test_locked_keeps_raw_and_dipping_workflow(self):
        self._lock()
        self.as_worker()

        # 原布：照旧登记浸渍
        resp = self.client.post("/api/dips/", dip_payload(self.raw.id), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

        # 原布→浸渍中、浸渍中→原布：照旧
        resp = self.client.patch(
            f"/api/rolls/{self.raw.id}/",
            {"status": ClothRoll.STATUS_DIPPING},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.client.patch(
            f"/api/rolls/{self.dipping.id}/",
            {"status": ClothRoll.STATUS_RAW},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        # 浸渍中：照旧登记浸渍
        resp = self.client.post("/api/dips/", dip_payload(self.dipping.id), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_unlocked_allows_dip_for_cured(self):
        # 未锁定时维持既有行为：已固化卷仍可登记浸渍
        self.as_worker()
        resp = self.client.post("/api/dips/", dip_payload(self.cured.id), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    # ---------- 并发：两笔同时登记同一已固化卷，必须双挡 ----------

    def test_concurrent_dips_both_blocked(self):
        self._lock()
        barrier = threading.Barrier(2)
        results = []

        def worker():
            client = APIClient()
            client.force_authenticate(self.worker)
            payload = dip_payload(self.cured.id)
            barrier.wait()
            resp = client.post("/api/dips/", payload, format="json")
            results.append(resp.status_code)
            connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(sorted(results), [400, 400])
        self.assertEqual(DipRun.objects.filter(roll=self.cured).count(), 1)
