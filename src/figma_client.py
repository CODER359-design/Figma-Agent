from __future__ import annotations

import time
from typing import Dict, Iterable, List, Optional

import requests


class FigmaClient:
    BASE_URL = "https://api.figma.com/v1"

    def __init__(self, token: str, *, max_retries: int = 3, backoff_base: float = 0.5) -> None:
        if not token:
            raise ValueError("FIGMA_TOKEN is required")
        self._session = requests.Session()
        self._session.headers.update({"X-Figma-Token": token})
        self._max_retries = max(1, max_retries)
        self._backoff_base = max(0.1, backoff_base)

    def get_file(self, file_key: str) -> Dict:
        return self._get_json(f"/files/{file_key}")

    def get_node(self, file_key: str, node_id: str) -> Dict:
        return self._get_json(f"/files/{file_key}/nodes", params={"ids": node_id})

    def get_images(
        self,
        file_key: str,
        node_ids: Iterable[str],
        image_format: str = "png",
        scale: int = 1,
    ) -> Dict[str, str]:
        ids_param = ",".join(node_ids)
        payload = {
            "ids": ids_param,
            "format": image_format,
            "scale": scale,
        }
        data = self._get_json(f"/images/{file_key}", params=payload)
        return data.get("images", {})

    def _get_json(self, path: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.BASE_URL}{path}"
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries):
            response = self._session.get(url, params=params, timeout=30)
            if response.status_code == 429 and attempt < self._max_retries - 1:
                sleep_for = self._backoff_base * (2 ** attempt)
                time.sleep(sleep_for)
                continue
            try:
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as error:  # type: ignore[assignment]
                last_error = error
                if attempt == self._max_retries - 1:
                    raise
                sleep_for = self._backoff_base * (2 ** attempt)
                time.sleep(sleep_for)
        if last_error:
            raise last_error
        raise RuntimeError("Unknown error while calling Figma API")


def chunk_ids(ids: List[str], size: int = 50) -> List[List[str]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]
