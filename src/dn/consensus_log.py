"""Append-only, hash-chained, HMAC-signed JSONL consensus log (IMPLEMENTATION.md section 13)."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

GENESIS = "0" * 64


def canonical_json(obj) -> str:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sign(role: str, message) -> str:
    """HMAC over the canonical message with its signature field blanked."""
    data = message.model_dump(mode="json") if hasattr(message, "model_dump") else dict(message)
    data["signature"] = ""
    key = config.ORG_KEYS[role].encode()
    return hmac.new(key, canonical_json(data).encode(), hashlib.sha256).hexdigest()


def verify_signature(role: str, message) -> bool:
    sig = message.signature if hasattr(message, "signature") else message.get("signature", "")
    return hmac.compare_digest(sig, sign(role, message))


def _entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256((entry["prev_hash"] + canonical_json(body)).encode()).hexdigest()


class ConsensusLog:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self.entries: list[dict] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                self.entries = read(self.path)

    def append(self, actor: str, turn: int, event, payload) -> dict:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        entry = {
            "seq": len(self.entries),
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "actor": actor, "turn": turn, "event": getattr(event, "value", event),
            "payload": json.loads(canonical_json(payload)),
            "prev_hash": self.entries[-1]["hash"] if self.entries else GENESIS,
        }
        entry["hash"] = _entry_hash(entry)
        self.entries.append(entry)
        if self.path:
            with self.path.open("a") as f:
                f.write(canonical_json(entry) + "\n")
        return entry

    def events(self, name: str) -> list[dict]:
        return [e for e in self.entries if e["event"] == name]


def read(path) -> list[dict]:
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


def verify_entries(entries: list[dict]) -> tuple[bool, int | None, str]:
    """Recompute the chain and every agent signature. Returns (ok, first_bad_seq, message)."""
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("seq") != i or e.get("prev_hash") != prev or _entry_hash(e) != e.get("hash"):
            return False, i, f"hash chain broken at entry {i}"
        msg = e["payload"].get("message") if isinstance(e.get("payload"), dict) else None
        if isinstance(msg, dict) and msg.get("signature") and msg.get("role") in config.ORG_KEYS:
            if not verify_signature(msg["role"], msg):
                return False, i, f"bad {msg['role']} signature at entry {i}"
        prev = e["hash"]
    return True, None, f"Log verified ({len(entries)} entries)"


def verify(path) -> tuple[bool, int | None, str]:
    return verify_entries(read(path))
