from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict


def record_trace(payload: Dict, html: str, css: str, trace_dir: str) -> None:
    """Persist normalized payload + outputs for fine-tuning/analysis."""
    os.makedirs(trace_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)
    trace_path = Path(trace_dir) / f"trace-{timestamp}.json"

    trace_payload = {
        "timestamp": timestamp,
        "normalized": payload,
        "html": html,
        "css": css,
    }

    with open(trace_path, "w", encoding="utf-8") as handle:
        json.dump(trace_payload, handle, ensure_ascii=False, indent=2)
