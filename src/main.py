from __future__ import annotations

import argparse
import json
import os
from typing import List

from dotenv import load_dotenv

from .assets import download_assets
from .figma_client import FigmaClient, chunk_ids
from .llm import LLMClient
from .normalize import normalize_figma
from .render import write_outputs
from .traces import record_trace


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Figma to HTML/CSS PoC")
    parser.add_argument("--file-key", default=os.getenv("FIGMA_FILE_KEY"))
    parser.add_argument("--node-id", default=os.getenv("FIGMA_NODE_ID"))
    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "output"))
    parser.add_argument("--dry-run", action="store_true", help="Only fetch and normalize")
    parser.add_argument(
        "--normalized-input",
        help="Path to an existing normalized JSON file (skips Figma fetch)",
    )
    parser.add_argument(
        "--record-trace",
        action="store_true",
        help="Save normalized payload + outputs for fine-tuning",
    )
    parser.add_argument(
        "--trace-dir",
        default=os.getenv("TRACE_DIR", "traces"),
        help="Directory to store trace json files",
    )
    parser.add_argument(
        "--export-assets",
        action="store_true",
        help="Download image assets referenced in the normalized JSON",
    )
    return parser.parse_args(argv)


def main() -> None:
    load_dotenv()
    args = parse_args()
    run_with_args(args)


def run_with_args(args: argparse.Namespace) -> None:
    _execute(args)


def _execute(args: argparse.Namespace) -> None:
    figma = None
    normalized = None

    if args.normalized_input:
        with open(args.normalized_input, "r", encoding="utf-8") as handle:
            normalized = json.load(handle)
    else:
        if not args.file_key:
            raise ValueError("FIGMA_FILE_KEY is required when not using --normalized-input")
        figma = FigmaClient(
            os.getenv("FIGMA_TOKEN", ""),
            max_retries=int(os.getenv("FIGMA_MAX_RETRIES", "3")),
            backoff_base=float(os.getenv("FIGMA_BACKOFF_BASE", "0.5")),
        )

        if args.node_id:
            figma_json = figma.get_node(args.file_key, args.node_id)
        else:
            figma_json = figma.get_file(args.file_key)

        normalized = normalize_figma(figma_json, args.node_id)

    section_tree = normalized.get("section") if isinstance(normalized, dict) else normalized
    if not section_tree:
        raise ValueError("Normalized payload missing 'section'")

    if figma:
        _inject_image_urls(figma, args.file_key, section_tree)

    if args.dry_run:
        write_outputs(normalized, "", "", args.output_dir)
        if args.record_trace:
            record_trace(normalized, "", "", args.trace_dir)
        return

    llm = LLMClient.from_env()
    html, css = llm.generate(normalized)
    write_outputs(normalized, html, css, args.output_dir)

    if args.record_trace:
        record_trace(normalized, html, css, args.trace_dir)

    if args.export_assets:
        assets = normalized.get("assets") if isinstance(normalized, dict) else None
        if assets:
            assets_dir = os.path.join(args.output_dir, "assets")
            download_assets(assets, assets_dir)


def _inject_image_urls(figma: FigmaClient, file_key: str, normalized: dict) -> None:
    image_nodes: List[dict] = []
    _collect_images(normalized, image_nodes)
    if not image_nodes:
        return

    ids = [node["figmaId"] for node in image_nodes if node.get("figmaId")]
    if not ids:
        return

    url_map = {}
    for chunk in chunk_ids(ids):
        url_map.update(figma.get_images(file_key, chunk))

    for node in image_nodes:
        figma_id = node.get("figmaId")
        node["url"] = url_map.get(figma_id)


def _collect_images(node: dict, bucket: List[dict]) -> None:
    if node.get("type") == "image":
        bucket.append(node)
    for child in node.get("children", []) or []:
        _collect_images(child, bucket)


if __name__ == "__main__":
    main()
