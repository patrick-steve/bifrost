"""HHMM <-> minutes since midnight."""
import math


def hhmm_to_min(hhmm) -> int:
    """1305 -> 785. 2400 -> 1440."""
    if hhmm is None or (isinstance(hhmm, float) and math.isnan(hhmm)):
        raise ValueError("missing HHMM value")
    v = int(hhmm)
    h, m = divmod(v, 100)
    if m >= 60 or h > 24:
        raise ValueError(f"invalid HHMM {hhmm}")
    return h * 60 + m


def arrival_after_departure(dep_min: int, arr_min: int, scheduled_time_min: int | None = None) -> int:
    """Times are local. Add a day only when that makes arrival - departure closer to the block time.

    Without a block time, an arrival earlier than departure means next day.
    """
    if scheduled_time_min is None:
        return arr_min + 1440 if arr_min < dep_min else arr_min
    same, nxt = arr_min - dep_min, arr_min + 1440 - dep_min
    return arr_min + 1440 if abs(nxt - scheduled_time_min) < abs(same - scheduled_time_min) else arr_min


def min_to_hhmm(minutes: int) -> str:
    """785 -> '13:05'; 1500 -> '01:00 +1'."""
    day, rem = divmod(int(minutes), 1440)
    s = f"{rem // 60:02d}:{rem % 60:02d}"
    return s + (f" +{day}" if day > 0 else "")
