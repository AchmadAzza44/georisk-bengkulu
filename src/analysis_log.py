"""Pencatatan hasil analisis (JSON Lines) agar eksekusi dapat ditelusuri: data (SHA-256), parameter, ringkasan hasil."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log_run(log_path: str | Path, params: dict[str, Any], summary: dict[str, Any], data_files: list[str | Path]) -> dict[str, Any]:
    entry = {
        "waktu_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "parameter": params, "ringkasan": summary,
        "data": {Path(f).name: file_sha256(f) for f in data_files},
    }
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def read_log(log_path: str | Path, last: int | None = None) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries[-last:] if last else entries
