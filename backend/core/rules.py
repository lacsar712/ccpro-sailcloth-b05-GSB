"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from .models import ClothRoll, CureLockSetting, DipRun

MIN_CURE_HOURS_FOR_CURED = Decimal("12")

CURE_LOCKED_DIP_MSG = "全站已固化挂签只读：该卷已固化，不能再登记浸渍"
CURE_LOCKED_STATUS_MSG = "全站已固化挂签只读：已固化卷不能改回浸渍中或原布"


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    """
    latest = latest_dip_run(roll)
    if latest is None:
        return False, "该布卷尚无浸渍记录，不能标记为已固化"
    if latest.cure_hours is None:
        return False, "最近浸渍记录尚未填写固化时长，不能标记为已固化"
    if latest.cure_hours < MIN_CURE_HOURS_FOR_CURED:
        return (
            False,
            f"最近浸渍固化时长 {latest.cure_hours} 小时低于 {MIN_CURE_HOURS_FOR_CURED} 小时，不能标记为已固化",
        )
    return True, ""


def cure_locked() -> bool:
    """全站「已固化挂签只读」是否开启。"""
    return CureLockSetting.is_locked()


def can_log_dip_for_roll(roll: ClothRoll) -> tuple[bool, str]:
    """固化锁定开启后，已固化卷不得再登记浸渍；其余状态照旧。"""
    if roll.status == ClothRoll.STATUS_CURED and cure_locked():
        return False, CURE_LOCKED_DIP_MSG
    return True, ""


def can_change_roll_status(
    roll: ClothRoll, new_status: str
) -> tuple[bool, str]:
    """固化锁定开启后，已固化卷不得改回浸渍中或原布。"""
    if (
        roll.status == ClothRoll.STATUS_CURED
        and new_status in (ClothRoll.STATUS_RAW, ClothRoll.STATUS_DIPPING)
        and cure_locked()
    ):
        return False, CURE_LOCKED_STATUS_MSG
    return True, ""
