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


def arrival_after_departure(dep_min: int, arr_min: int) -> int:
    """A scheduled arrival earlier than the departure means next day."""
    return arr_min + 1440 if arr_min < dep_min else arr_min


def min_to_hhmm(minutes: int) -> str:
    """785 -> '13:05'; 1500 -> '01:00 +1'."""
    day, rem = divmod(int(minutes), 1440)
    s = f"{rem // 60:02d}:{rem % 60:02d}"
    return s + (f" +{day}" if day > 0 else "")
