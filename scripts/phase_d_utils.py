#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


EXTRACTION_JSON_BEGIN = "===EXTRACTION JSON BEGIN==="
EXTRACTION_JSON_END = "===EXTRACTION JSON END==="
RATIO_PRESETS = {
    "16:9": 16 / 9,
    "4:3": 4 / 3,
    "3:2": 3 / 2,
    "1:1": 1.0,
}


def load_extraction_payload(input_path: Path) -> dict[str, Any]:
    text = input_path.read_text(encoding="utf-8", errors="surrogateescape")
    json_text = extract_wrapped_json(text)
    data = sanitize_json_value(json.loads(json_text))
    if not isinstance(data, dict):
        raise SystemExit(f"顶层必须是 JSON object: {input_path}")
    return data


def extract_wrapped_json(text: str) -> str:
    begin = text.find(EXTRACTION_JSON_BEGIN)
    end = text.find(EXTRACTION_JSON_END)
    if begin != -1 and end != -1 and begin < end:
        return text[begin + len(EXTRACTION_JSON_BEGIN):end].strip()
    return text.strip()


def dump_json(output_path: Path, data: Any) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(sanitize_json_value(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def infer_aspect_ratio(width: float, height: float) -> str:
    if width <= 0 or height <= 0:
        return "16:9"
    ratio = width / height
    return min(RATIO_PRESETS, key=lambda label: abs(RATIO_PRESETS[label] - ratio))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_bbox(bbox: tuple[float, float, float, float], width: float, height: float) -> list[float]:
    x0, y0, x1, y1 = bbox
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 1.0, 1.0]
    x = clamp01(x0 / width)
    y = clamp01(y0 / height)
    w = clamp01((x1 - x0) / width)
    h = clamp01((y1 - y0) / height)
    if x + w > 1:
        w = max(0.0, 1.0 - x)
    if y + h > 1:
        h = max(0.0, 1.0 - y)
    return [round(x, 4), round(y, 4), round(w, 4), round(h, 4)]


def resolve_asset_path(ref: str, manifest_path: Path) -> Path:
    if not ref:
        raise SystemExit("资源路径不能为空")
    parsed = urlparse(ref)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).resolve()
    candidate = Path(ref)
    if candidate.is_absolute():
        return candidate.resolve()

    if len(candidate.parts) > 1 and candidate.parts[0] == manifest_path.parent.name:
        normalized_relative = (manifest_path.parent / Path(*candidate.parts[1:])).resolve()
        if normalized_relative.exists():
            return normalized_relative

    manifest_relative = (manifest_path.parent / candidate).resolve()
    if manifest_relative.exists():
        return manifest_relative

    cwd_relative = (Path.cwd() / candidate).resolve()
    if cwd_relative.exists():
        return cwd_relative

    return manifest_relative


def sanitize_text(text: str) -> str:
    cleaned_chars: list[str] = []
    for char in text:
        codepoint = ord(char)
        if codepoint in (0x09, 0x0A, 0x0D):
            cleaned_chars.append(char)
            continue
        if 0x00 <= codepoint <= 0x1F:
            continue
        if 0x7F <= codepoint <= 0x9F:
            continue
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        if 0xFDD0 <= codepoint <= 0xFDEF:
            continue
        if codepoint & 0xFFFF in (0xFFFE, 0xFFFF):
            continue
        cleaned_chars.append(char)
    return "".join(cleaned_chars)


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            sanitize_text(str(key)) if not isinstance(key, str) else sanitize_text(key): sanitize_json_value(val)
            for key, val in value.items()
        }
    return value


def serialize_inline_json(data: Any) -> str:
    serialized = json.dumps(sanitize_json_value(data), ensure_ascii=False, indent=2)
    return (
        serialized
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def serialize_html_json_payload(data: Any) -> str:
    return serialize_inline_json(data).replace("<!--", "<\\!--")
