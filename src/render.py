from __future__ import annotations

import json
import os
from typing import Dict


def write_outputs(normalized: Dict, html: str, css: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    normalized_path = os.path.join(output_dir, "normalized.json")
    html_path = os.path.join(output_dir, "section.html")
    css_path = os.path.join(output_dir, "styles.css")
    preview_path = os.path.join(output_dir, "preview.html")

    with open(normalized_path, "w", encoding="utf-8") as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)

    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    with open(css_path, "w", encoding="utf-8") as handle:
        handle.write(css)

    preview_html = _build_preview(html, css)
    with open(preview_path, "w", encoding="utf-8") as handle:
        handle.write(preview_html)


def _build_preview(html: str, css: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Figma PoC Preview</title>
  <style>{css}</style>
</head>
<body>
  {html}
</body>
</html>
"""
