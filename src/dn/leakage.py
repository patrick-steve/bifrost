"""Leakage scan over logged prompts (IMPLEMENTATION.md section 15, integrity test)."""
from __future__ import annotations

import json
import re

from . import config

# Sealed time-of-day columns: their HHMM values are distinctive enough to scan for.
_TIME_COLS = ("ARRIVAL_TIME", "WHEELS_ON", "WHEELS_OFF", "DEPARTURE_TIME")


def scan(prompts: list[dict], sealed) -> list[str]:
    """Return hits. Column names: exact uppercase anywhere, lowercase as a JSON key.
    Values: sealed HHMM times appearing as JSON values of a time-like key."""
    text = json.dumps(prompts)
    hits = []
    for col in config.SEALED_COLUMNS:
        if re.search(rf"\b{col}\b", text):
            hits.append(f"column name {col}")
        if f'\\"{col.lower()}\\"' in text or f'"{col.lower()}"' in text:
            hits.append(f"column key {col.lower()}")
    for col in _TIME_COLS:
        v = (sealed.raw or {}).get(col)
        if v is None:
            continue
        for p in prompts:
            if re.search(rf'(arrival|departure|time|wheels)[a-z_]*\\?"\s*:\s*{int(v)}\b', p.get("user", "")):
                hits.append(f"value {col}={int(v)}")
    return hits
