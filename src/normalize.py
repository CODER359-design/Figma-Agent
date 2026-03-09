from __future__ import annotations

from typing import Any, Dict, List, Optional


def normalize_figma(figma_json: Dict[str, Any], node_id: Optional[str] = None) -> Dict[str, Any]:
    document = _extract_document(figma_json, node_id)
    frame = _find_first_frame(document)
    if not frame:
        raise ValueError("No frame found in Figma document")
    section = _normalize_section(frame)
    root_class = f"section-{section['name']}"
    _enrich_tree(section, root_class)

    assets: List[Dict[str, Any]] = []
    _collect_assets(section, assets)

    summary = _build_summary(section)

    return {
        "section": section,
        "assets": assets,
        "summary": summary,
    }


def _extract_document(figma_json: Dict[str, Any], node_id: Optional[str]) -> Dict[str, Any]:
    if "nodes" in figma_json:
        node_data = figma_json.get("nodes", {}).get(node_id or "", {})
        return node_data.get("document") or {}
    return figma_json.get("document") or {}


def _find_first_frame(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not node:
        return None

    if node.get("type") in {"FRAME", "COMPONENT", "INSTANCE"}:
        return node
    for child in node.get("children", []) or []:
        result = _find_first_frame(child)
        if result:
            return result
    return None


def _enrich_tree(node: Dict[str, Any], root_class: str, path: Optional[List[str]] = None, depth: int = 0) -> None:
    slug = _slug(node.get("name") or node.get("type", "node"))
    current_path = (path or []) + [slug]
    if depth == 0:
        node["className"] = root_class
    else:
        suffix = "-".join(current_path[1:]) if len(current_path) > 1 else slug
        node["className"] = f"{root_class}__{suffix}" if suffix else root_class
    node["dataPath"] = "/".join(current_path)
    node["role"] = _infer_role(node)
    node["depth"] = depth

    children = node.get("children", []) or []
    for index, child in enumerate(children):
        _enrich_tree(child, root_class, current_path, depth + 1)
        child["order"] = index


def _collect_assets(node: Dict[str, Any], bucket: List[Dict[str, Any]]) -> None:
    if node.get("type") == "image" and node.get("url"):
        bucket.append(
            {
                "name": node.get("name"),
                "figmaId": node.get("figmaId"),
                "className": node.get("className"),
                "role": node.get("role"),
                "url": node.get("url"),
            }
        )
    for child in node.get("children", []) or []:
        _collect_assets(child, bucket)


def _build_summary(node: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}

    def _walk(current: Dict[str, Any]) -> None:
        node_type = current.get("type", "unknown")
        counts[node_type] = counts.get(node_type, 0) + 1
        for child in current.get("children", []) or []:
            _walk(child)

    _walk(node)
    total = sum(counts.values())
    return {"totalNodes": total, "byType": counts}
    if node.get("type") in {"FRAME", "COMPONENT", "INSTANCE"}:
        return node
    for child in node.get("children", []) or []:
        result = _find_first_frame(child)
        if result:
            return result
    return None


def _normalize_section(node: Dict[str, Any]) -> Dict[str, Any]:
    section = {
        "type": "section",
        "name": _slug(node.get("name", "section")),
        "figmaId": node.get("id"),
        "layout": _extract_layout(node),
        "children": [],
    }
    for child in node.get("children", []) or []:
        normalized = _normalize_node(child)
        if normalized:
            section["children"].append(normalized)
    return section


def _normalize_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not node.get("visible", True):
        return None

    if _is_text(node):
        return _normalize_text(node)
    if _is_input(node):
        return _normalize_input(node)
    if _is_button(node):
        return _normalize_button(node)
    if _is_image(node):
        return _normalize_image(node)

    children = []
    for child in node.get("children", []) or []:
        normalized = _normalize_node(child)
        if normalized:
            children.append(normalized)

    if children:
        return {
            "type": "container",
            "name": _slug(node.get("name", "container")),
            "figmaId": node.get("id"),
            "layout": _extract_layout(node),
            "children": children,
        }
    return None


def _normalize_text(node: Dict[str, Any]) -> Dict[str, Any]:
    style = node.get("style", {})
    font_size = style.get("fontSize") or 16
    text_type = "heading" if font_size >= 28 or _name_contains(node, ["title", "heading", "hero"]) else "paragraph"
    return {
        "type": text_type,
        "name": _slug(node.get("name", text_type)),
        "text": node.get("characters", ""),
        "style": {
            "fontSize": font_size,
            "fontWeight": style.get("fontWeight"),
            "lineHeight": style.get("lineHeightPx"),
            "textAlign": style.get("textAlignHorizontal"),
            "letterSpacing": style.get("letterSpacing"),
            "fills": _extract_fills(node),
        },
    }


def _normalize_button(node: Dict[str, Any]) -> Dict[str, Any]:
    text_child = _find_first_text(node)
    return {
        "type": "button",
        "name": _slug(node.get("name", "button")),
        "text": (text_child or {}).get("characters", "Button"),
        "layout": _extract_layout(node),
        "style": {
            "fills": _extract_fills(node),
            "strokes": _extract_strokes(node),
            "cornerRadius": node.get("cornerRadius"),
        },
    }


def _normalize_input(node: Dict[str, Any]) -> Dict[str, Any]:
    text_child = _find_first_text(node)
    return {
        "type": "input",
        "name": _slug(node.get("name", "input")),
        "placeholder": (text_child or {}).get("characters", ""),
        "layout": _extract_layout(node),
        "style": {
            "fills": _extract_fills(node),
            "strokes": _extract_strokes(node),
            "cornerRadius": node.get("cornerRadius"),
        },
    }


def _normalize_image(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "image",
        "name": _slug(node.get("name", "image")),
        "figmaId": node.get("id"),
        "layout": _extract_layout(node),
        "imageRef": _extract_image_ref(node),
    }


def _extract_layout(node: Dict[str, Any]) -> Dict[str, Any]:
    box = node.get("absoluteBoundingBox", {}) or {}
    return {
        "mode": node.get("layoutMode"),
        "padding": {
            "top": node.get("paddingTop"),
            "right": node.get("paddingRight"),
            "bottom": node.get("paddingBottom"),
            "left": node.get("paddingLeft"),
        },
        "spacing": node.get("itemSpacing"),
        "align": {
            "primary": node.get("primaryAxisAlignItems"),
            "counter": node.get("counterAxisAlignItems"),
        },
        "width": box.get("width"),
        "height": box.get("height"),
    }


def _is_text(node: Dict[str, Any]) -> bool:
    return node.get("type") == "TEXT"


def _is_button(node: Dict[str, Any]) -> bool:
    if node.get("type") not in {"FRAME", "COMPONENT", "INSTANCE"}:
        return False
    if _name_contains(node, ["button", "btn", "cta"]):
        return True

    if not _looks_like_button_dimensions(node):
        return False

    text_child = _find_first_text(node)
    if not text_child:
        return False

    fills = _extract_fills(node)
    if not fills:
        return False

    children = node.get("children", []) or []
    non_text_children = [child for child in children if child.get("type") != "TEXT"]
    if non_text_children:
        return False

    return True


def _is_input(node: Dict[str, Any]) -> bool:
    if node.get("type") not in {"FRAME", "COMPONENT", "INSTANCE"}:
        return False

    if _name_contains(node, ["input", "field", "form", "type", "phone", "email", "search", "message"]):
        return True

    text_child = _find_first_text(node)
    if not text_child:
        return False

    placeholder = (text_child.get("characters") or "").strip().lower()
    if _looks_like_input_placeholder(placeholder):
        return True

    return False


def _is_image(node: Dict[str, Any]) -> bool:
    if node.get("type") in {"RECTANGLE", "VECTOR", "IMAGE"} and _extract_image_ref(node):
        return True
    return _name_contains(node, ["image", "img", "icon", "photo"]) and node.get("type") in {
        "RECTANGLE",
        "VECTOR",
        "FRAME",
    }


def _find_first_text(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for child in node.get("children", []) or []:
        if child.get("type") == "TEXT":
            return child
    return None


def _extract_fills(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    fills = []
    for fill in node.get("fills", []) or []:
        if fill.get("visible", True) is False:
            continue
        fill_color = fill.get("color")
        fills.append(
            {
                "type": fill.get("type"),
                "color": _color_to_rgba(fill_color, fill.get("opacity")),
            }
        )
    return fills


def _extract_strokes(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    strokes = []
    for stroke in node.get("strokes", []) or []:
        if stroke.get("visible", True) is False:
            continue
        strokes.append(
            {
                "type": stroke.get("type"),
                "color": _color_to_rgba(stroke.get("color"), stroke.get("opacity")),
            }
        )
    return strokes


def _extract_image_ref(node: Dict[str, Any]) -> Optional[str]:
    for fill in node.get("fills", []) or []:
        if fill.get("type") == "IMAGE":
            return fill.get("imageRef")
    return None


def _color_to_rgba(color: Optional[Dict[str, Any]], opacity: Optional[float]) -> Optional[str]:
    if not color:
        return None
    r = int(color.get("r", 0) * 255)
    g = int(color.get("g", 0) * 255)
    b = int(color.get("b", 0) * 255)
    a = opacity if opacity is not None else color.get("a", 1)
    return f"rgba({r}, {g}, {b}, {a})"


def _name_contains(node: Dict[str, Any], needles: List[str]) -> bool:
    name = (node.get("name") or "").lower()
    return any(n in name for n in needles)


def _slug(value: str) -> str:
    return "-".join(value.lower().strip().replace("/", " ").split())


def _looks_like_button_dimensions(node: Dict[str, Any]) -> bool:
    box = node.get("absoluteBoundingBox") or {}
    width = box.get("width") or 0
    height = box.get("height") or 0
    return width <= 400 and height <= 120


def _looks_like_input_placeholder(text: str) -> bool:
    if not text:
        return False
    keywords = [
        "your",
        "email",
        "phone",
        "name",
        "search",
        "number",
        "message",
    ]
    return any(keyword in text for keyword in keywords)


def _infer_role(node: Dict[str, Any]) -> str:
    node_type = node.get("type")
    name = (node.get("name") or "").lower()

    if node_type == "section":
        return "section"
    if node_type == "heading":
        if "hero" in name or "title" in name:
            return "hero-heading"
        return "heading"
    if node_type == "paragraph":
        if "menu" in name or "nav" in name:
            return "nav-link"
        return "text"
    if node_type == "button":
        if "cta" in name or "explore" in (node.get("text") or "").lower():
            return "cta"
        return "button"
    if node_type == "input":
        return "input"
    if node_type == "image":
        if "logo" in name:
            return "logo"
        if "card" in name:
            return "product-image"
        return "image"
    if node_type == "container":
        if "header" in name or "menu" in name:
            return "navigation"
        if "footer" in name:
            return "footer"
        if "card" in name:
            return "card"
        if "last-block" in name or "cta" in name:
            return "cta-wrapper"
    return node_type or "node"
