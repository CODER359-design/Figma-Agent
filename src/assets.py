from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable

import requests


def download_assets(assets: Iterable[Dict], output_dir: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    for asset in assets:
        url = asset.get("url")
        name = asset.get("name") or asset.get("figmaId") or "asset"
        if not url:
            continue

        slug = name.lower().replace(" ", "-")
        filepath = Path(output_dir) / f"{slug}.png"

        response = session.get(url, timeout=30)
        response.raise_for_status()

        with open(filepath, "wb") as handle:
            handle.write(response.content)
